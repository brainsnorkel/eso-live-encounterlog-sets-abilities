#!/usr/bin/env python3
"""Check the fight re-reader (src/fight_reread.py) against the engine on
real split logs: a local tool, like the replay compare, run after any
change to the engine's identity rules, its locator or the log format.

    python -X utf8 scripts/check_fight_reread.py <src dir> <logs.tsv | log ...> <out dir>
        [--workers 4] [--zip STAMP ...] [--zip-dir DIR]

<src dir> is the src/ to check (data/ beside it); a .tsv lists the logs
(path in the last column, '#' lines skipped). Each log runs in a process
of its own, at most --workers at a time. The tool writes only into <out
dir> (per log, check-<log name>.json and run-<log name>.txt with the
worker's errors, named by the log's whole file name, as several splits
share a session's stamp; and summary.txt, which names each log whose
check failed) and the --zip-dir, and prints zones and bosses, never a
player's name. Two logs with the same file name stop the tool before it
starts. A fight no place gives (NotOnDisk) is recorded as 'not found',
with the reasons, and the log goes on.

Per log, the engine reads the split twice, as a review reads it
(review_load.replay_log, the app's default settings):
  1. to learn every fight's locator (entry.locator), from which each
     fight's range is worked out here, independently of the reader, from
     the file's own lines: the first line at start - LEAD_MS after the
     zone's line (a ZONE_CHANGED in the lead-in starting it again), to the
     first line after end + TAIL_MS or the next BEGIN_COMBAT, ZONE_CHANGED,
     BEGIN_LOG or END_LOG after the END_COMBAT line. The lines the locator
     names are checked too;
  2. with an oracle, which records for every unit state on every line in
     a fight's range the engine's own fields and its identity of the unit
     at that line (CombatEncounter.player_of, companion_units,
     pet_ownership, enemies) and builds each unit's expected track by the
     reader's rules from those fields. At the fight's build it maps each
     row of the unit table to the engine's object.
Then each fight is re-read from the split (read_fight) and compared: every
track's columns byte for byte with the expected track of the same row (or
unknown unit id); the identity of every state occurrence, unit and owner,
the table's against the engine's; found_by, the range's first time and
whether the tail was seen, the frames; the time to read and the bytes a
state. The same fight is read again with its offsets spoiled by 13 bytes,
found by time, and must be identical. With --zip, those splits are zipped
as split retention zips them (a copy, in --zip-dir, deleted after) and
every fight read from the zip, by offset and by time, must equal the plain
read.
"""

import argparse
import gc
import json
import os
import shutil
import subprocess
import sys
import time
from array import array
from bisect import bisect_left
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STATE_AT = {"COMBAT_EVENT": (7, 17), "EFFECT_CHANGED": (4, 14), "BEGIN_CAST": (4, 14),
            "HEALTH_REGEN": (1, None)}
SPECIAL = {b"BEGIN_LOG", b"END_LOG", b"ZONE_CHANGED", b"BEGIN_COMBAT", b"END_COMBAT"}
SPOIL = 13
FOREVER = 1 << 62


# ------------------------------------------------------- the range, here --

def index_lines(path):
    """Every line's offset and time, and the kind of the lines a range
    turns on, from the file's bytes."""
    offsets, times, special = array("q"), array("q"), {}
    pos = 0
    with open(path, "rb") as f:
        for raw in f:
            head, _, rest = raw.partition(b",")
            index = len(offsets)
            offsets.append(pos)
            times.append(int(head) if head.isdigit() else -1)
            kind = rest.split(b",", 1)[0].rstrip(b"\r\n")
            if kind in SPECIAL:
                special[index] = (kind, raw.rstrip(b"\r\n"))
            pos += len(raw)
    return offsets, times, special, pos


def oracle_range(lines, loc, lead_ms, tail_ms):
    """(first offset, stop offset, the first line's time, tail seen,
    problems) of the fight's range, by the rules in the module."""
    offsets, times, special, size = lines
    problems = []

    def line_at(offset, kind, text=None):
        i = bisect_left(offsets, offset)
        if i >= len(offsets) or offsets[i] != offset:
            problems.append(f"{kind.decode()} offset not a line start")
            return None
        got = special.get(i)
        if got is None or got[0] != kind or (text is not None and got[1] != text):
            problems.append(f"{kind.decode()} line not at its offset")
        return i

    base = loc.session_offset
    if base is None or loc.session_epoch_ms is None:
        return None, None, None, None, ["session not known"]
    i_base = line_at(base, b"BEGIN_LOG")
    if i_base is not None and special.get(i_base, (b"", b""))[1].split(b",")[2:3] != [
            b"%d" % loc.session_epoch_ms]:
        problems.append("BEGIN_LOG of another session")
    if loc.begin_offset is not None:
        i_begin = line_at(base + loc.begin_offset, b"BEGIN_COMBAT",
                          b"%d,BEGIN_COMBAT" % loc.start_ms)
        i_floor = (line_at(base + loc.zone_offset, b"ZONE_CHANGED")
                   if loc.zone_offset is not None else i_base)
    elif i_base is None:
        return None, None, None, None, problems
    else:
        i_begin = next((i for i in range(i_base + 1, len(times)) if times[i] >= loc.start_ms),
                       None)
        if i_begin is None:
            problems.append("no line at the start")
        i_floor = i_base
    if None in (i_base, i_begin, i_floor):
        return None, None, None, None, problems
    from_ms = loc.start_ms - lead_ms
    start = next((i for i in range(i_floor, i_begin + 1) if times[i] >= from_ms), i_begin)
    for i in range(start + 1, i_begin):
        if i in special and special[i][0] == b"ZONE_CHANGED":
            start = i
    if loc.end_offset is not None:
        i_end = line_at(base + loc.end_offset, b"END_COMBAT", b"%d,END_COMBAT" % loc.end_ms)
    else:
        i_end = next((i for i in range(i_begin + 1, len(times)) if special.get(i, (b"", b""))[1]
                      == b"%d,END_COMBAT" % loc.end_ms), None)
    if i_end is None:
        return None, None, None, None, problems + ["no END_COMBAT"]
    for i in range(i_begin + 1, i_end):
        if i in special and special[i][0] in (b"ZONE_CHANGED", b"BEGIN_LOG", b"END_LOG"):
            problems.append("a session or zone line inside the fight")
    stop, seen = len(offsets), False
    for i in range(i_end + 1, len(offsets)):
        if times[i] > loc.end_ms + tail_ms or (i in special and special[i][0] != b"END_COMBAT"):
            stop, seen = i, True
            break
    stop_offset = offsets[stop] if stop < len(offsets) else size
    return offsets[start], stop_offset, times[start], seen, problems


# ------------------------------------------------------------ the oracle --

class Expected:
    """One track by the reader's rules, from the engine's str fields."""
    __slots__ = ("columns", "last", "pending", "uids")

    def __init__(self, codes):
        self.pending = None
        self.last = None
        self.columns = [array(code) for code in codes]
        self.uids = set()

    def add(self, t, frame, raw):
        pending = self.pending
        if pending is None:
            self.pending = [t, frame, raw, t]
        elif pending[1] == frame and raw == pending[2]:
            pending[3] = t  # written again: seen later
        elif pending[0] == t and pending[1] == frame:
            pending[2], pending[3] = raw, t
        else:
            self._append(pending)
            self.pending = [t, frame, raw, t]

    def _append(self, pending):
        t, frame, raw, seen = pending
        if self.last == (frame, raw):
            self.columns[-1][-1] = max(self.columns[-1][-1], seen)
            return
        self.last = (frame, raw)
        hp, _, hp_max = raw[0].partition("/")
        mg, _, mg_max = raw[1].partition("/")
        st, _, st_max = raw[2].partition("/")
        values = (t, float(raw[6]), float(raw[7]), float(raw[8]), int(hp), int(hp_max or 0),
                  int(mg), int(mg_max or 0), int(st), int(st_max or 0),
                  int(raw[3].partition("/")[0]), int(raw[5]), frame, seen)
        for column, value in zip(self.columns, values):
            column.append(value)

    def close(self):
        if self.pending is not None:
            self._append(self.pending)
            self.pending = None
        return [column.tobytes() for column in self.columns]


class Window:
    """One fight's range as the oracle replay passes it."""

    def __init__(self, key, start, stop, first_frame, codes):
        self.key = key
        self.start = start
        self.stop = stop
        self.frames = [first_frame]
        self.codes = codes
        self.occ = defaultdict(lambda: array("q"))  # (uid, id(unit), id(owner)) -> times
        self.builders = {}                          # id(unit) -> Expected
        self.objects = {}                           # id -> the object, kept alive

    def state(self, t, uid, unit, owner, raw):
        # An engine record by identity; a unit it has no record of by its id
        key = unit if isinstance(unit, str) else id(unit)
        self.objects[key] = unit
        self.objects[id(owner)] = owner
        self.occ[(uid, key, id(owner))].append(t)
        builder = self.builders.get(key)
        if builder is None:
            builder = self.builders[key] = Expected(self.codes)
        builder.uids.add(uid)
        builder.add(t, len(self.frames) - 1, raw)


def engine_identity(enc, uid):
    """The engine's unit for *uid* now (a player, a companion record, an
    enemy record, else the id itself) and the owner it gives a pet."""
    if enc is None:
        return uid, None
    player = enc.player_of(uid)
    if player is not None:
        return player, None
    key = enc.companion_units.get(uid)
    record = enc.companions.get(key) if key is not None else None
    if record is not None:
        return record, None
    owner_key = enc.pet_ownership.get(uid)
    owner = enc.players.get(owner_key) if owner_key is not None else None
    enemy = enc.enemies.get(uid)
    return (enemy if enemy is not None else uid), owner


def table_row(units, uid, t):
    """The reader's rule, written again: the row naming *uid* whose window
    holds *t*, the latest arrival winning."""
    best = None
    for index, unit in enumerate(units):
        if uid in unit.ids:
            since = -FOREVER if unit.since_ms is None else unit.since_ms
            until = FOREVER if unit.until_ms is None else unit.until_ms
            if since <= t <= until and (best is None or since >= best[0]):
                best = (since, index)
    return None if best is None else best[1]


def make_oracle(esolog_tail, fight_locator):
    """The engine class, watched (see the module)."""
    player_kinds = (fight_locator.SELF, fight_locator.GROUP, fight_locator.PLAYER)

    class Oracle(esolog_tail.ESOLogAnalyzer):

        def watch(self, windows, codes):
            self.waiting = sorted(windows, key=lambda w: w.start)
            self.open = []
            self.done = {}
            self.row_maps = {}
            self.codes = codes

        def _fight_locator(self, enc):
            locator = super()._fight_locator(enc)
            start = enc.located
            roster = [player for player, _ids in start.roster] if start is not None else []
            players = list(enc.players.values()) + roster
            enemies = list(enc.enemies.values()) + [unit for unit, _when in self._replaced_units]
            objects, owners = [], []
            for unit in locator.units:
                owner = None
                if unit.kind in player_kinds:
                    found = [p for p in players if p.unit_id == unit.key]
                    exact = [p for p in found
                             if (p.joined_at, p.left_at) == (unit.since_ms, unit.until_ms)]
                    obj = (exact or found or [None])[0]
                elif unit.kind == fight_locator.COMPANION:
                    obj = enc.companions.get(unit.key)
                    if obj is not None:
                        owner = next((p for p in players if p.unit_id == obj.owner_unit_id), None)
                else:
                    found = [e for e in enemies if e.unit_id == unit.key]
                    exact = [e for e in found if e.added_at == unit.since_ms]
                    obj = (exact or found or [None])[0]
                    owner = obj.owner_player if obj is not None and unit.owner else None
                objects.append(obj)
                owners.append(owner)
            self.row_maps[(locator.session_epoch_ms, locator.start_ms)] = (locator, objects, owners)
            return locator

        def process_log_entry(self, entry):
            super().process_log_entry(entry)
            offset = self.line_offset
            if entry is None or offset is None:
                return
            while self.waiting and self.waiting[0].start <= offset:
                self.open.append(self.waiting.pop(0))
            for window in [w for w in self.open if w.stop <= offset]:
                self.close(window)
            if not self.open:
                return
            kind = entry.event_type
            if kind == "MAP_CHANGED":
                frame = fight_locator.MapFrame(*(list(entry.fields[:3]) + ["", "", ""])[:3])
                for window in self.open:
                    window.frames.append(frame)
            elif kind in STATE_AT:
                fields = entry.fields
                line = entry.original_line
                t = int(line[:line.index(",")])
                enc = self.current_encounter
                for at in STATE_AT[kind]:
                    if at is None or len(fields) <= at + 9 or fields[at] in ("0", "*"):
                        continue
                    raw = tuple(fields[at + 1:at + 10])
                    if raw[0] == "1/1" and raw[6] == "0.0000" and raw[7] == "0.0000":
                        continue
                    unit, owner = engine_identity(enc, fields[at])
                    for window in self.open:
                        window.state(t, fields[at], unit, owner, raw)

        def close(self, window):
            self.open.remove(window)
            self.done[window.key] = window
            found = self.row_maps.get(window.key[:2])
            window.result = judge(window, found, player_kinds, fight_locator.COMPANION)
            window.occ = window.builders = window.objects = None

        def close_all(self):
            for window in list(self.open) + self.waiting:
                self.close(window)
            self.waiting = []

    return Oracle


def judge(window, found, player_kinds, companion):
    """At a window's end: its expected tracks by table key, and the
    identity of each state occurrence against the table's."""
    if found is None:
        return {"error": "no unit table for the fight"}
    locator, objects, owners = found
    if locator != window.key[2]:
        return {"error": "locator differs between the two replays"}
    row_of = {id(obj): index for index, obj in enumerate(objects) if obj is not None}
    expected, collisions = {}, 0
    for key, builder in window.builders.items():
        row = row_of.get(key)
        if row is None:
            obj = window.objects[key]
            uid = obj if isinstance(obj, str) else getattr(obj, "unit_id", None)
            row = ("unknown", uid if len(builder.uids) == 1 else f"several {sorted(builder.uids)}")
        if row in expected:
            collisions += 1
            expected[row] = None
        else:
            expected[row] = builder.close()
    agree, causes, owner_bad, windows = 0, Counter(), Counter(), Counter()
    units = locator.units
    naming = Counter(uid for unit in units for uid in unit.ids)
    for (uid, unit_key, owner_key), times in window.occ.items():
        engine_row = row_of.get(unit_key)
        obj = window.objects[unit_key]
        owner = window.objects[owner_key]
        for t in times:
            row = table_row(units, uid, t)
            if naming[uid] > 1:
                windows["on an id two or more rows name"] += 1
            if row is None and naming[uid]:
                windows["outside every window of the rows naming the id"] += 1
            if row != engine_row:
                engine_kind = (units[engine_row].kind if engine_row is not None
                               else "id" if isinstance(obj, str) else type(obj).__name__)
                causes[f"table {units[row].kind if row is not None else 'none'}, "
                       f"engine {engine_kind}"] += 1
                continue
            agree += 1
            if row is None or units[row].kind in player_kinds or units[row].kind == companion:
                continue
            table_owner = owners[row]
            if table_owner is not owner:
                owner_bad["table has one, engine none" if owner is None
                          else "engine has one, table none" if table_owner is None
                          else "another"] += 1
    return {"expected": expected, "collisions": collisions, "agree": agree,
            "causes": causes, "owner_bad": owner_bad, "windows": windows,
            "unmapped_rows": sum(1 for obj in objects if obj is None)}


# ------------------------------------------------------------- one log --

def columns_of(states, fr):
    return {(track._row if track._row >= 0 else ("unknown", track.ids[0])):
            [bytes(getattr(track, name)) for name, _code in fr.STATE_COLUMNS]
            for track in states.tracks}


def same_read(a, b, fr):
    return (columns_of(a, fr) == columns_of(b, fr) and a.frames == b.frames
            and (a.range_start_ms, a.tail_seen) == (b.range_start_ms, b.tail_seen))


def reasons_of(exc):
    """A NotOnDisk's reasons, one 'kind file: why' each."""
    return [f"{place.kind} {place.path.name}: {why}" for place, why in exc.reasons]


def build_analyzer(cls, out_dir):
    from app_config import AppConfig
    from app_startup import build_analyzer as app_build
    analyzer = app_build(AppConfig(path=Path(out_dir) / "no-such-config.json"), [])
    analyzer.__class__ = cls
    return analyzer


def check_log(src, log, out_json, zip_dir=None):
    sys.path.insert(0, src)
    sys.dont_write_bytecode = True
    import esolog_tail
    import fight_locator
    import fight_reread as fr
    import review_load
    import split_retention

    out_dir = os.path.dirname(out_json)
    codes = [code for _name, code in fr.STATE_COLUMNS]
    stats = Counter()
    rejected = Counter()

    def replay(analyzer):
        parser = analyzer.log_parser
        parse = parser.parse_line

        def counted(line):
            entry = parse(line)
            if entry is None and line:
                rejected[line.split(",", 2)[1] if line.count(",") >= 1 else "?"] += 1
            return entry

        parser.parse_line = counted
        began = time.perf_counter()
        with open(os.devnull, "w", encoding="utf-8") as quiet:
            stdout, sys.stdout = sys.stdout, quiet
            try:
                _shown, fights = review_load.replay_log(analyzer, Path(log))
            finally:
                sys.stdout = stdout
        return fights, time.perf_counter() - began

    # 1. The locators, and the ranges worked out here
    first, replay1_s = replay(build_analyzer(esolog_tail.ESOLogAnalyzer, out_dir))
    lines = index_lines(log)
    windows, ranges = [], {}
    for entry in first:
        loc = entry.locator
        start, stop, start_ms, seen, problems = oracle_range(lines, loc, fight_locator.LEAD_MS,
                                                             fight_locator.TAIL_MS)
        key = (loc.session_epoch_ms, loc.start_ms, loc)
        ranges[key[:2]] = (start, stop, start_ms, seen, problems)
        if start is not None:
            windows.append(Window(key, start, stop, loc.map_at_lead or fr.UNKNOWN_MAP, codes))
    del lines
    rejected.clear()

    # 2. The oracle replay
    oracle = build_analyzer(make_oracle(esolog_tail, fight_locator), out_dir)
    oracle.watch(windows, codes)
    second, replay2_s = replay(oracle)
    oracle.close_all()
    # What the rest needs of the fights; the engines go before anything is
    # timed (a heap of live engine objects slows every collection)
    first_locators = {(e.locator.session_epoch_ms, e.locator.start_ms): e.locator for e in first}
    fights = []
    for entry in second:
        loc = entry.locator
        players = sum(1 for row in entry.players if not row.get("companion"))
        fights.append((loc, entry.zone_name, entry.boss_name, entry.duration_s, players,
                       bool(entry.pull) and players >= 10,
                       oracle.done.get((loc.session_epoch_ms, loc.start_ms, loc))))
    del first, second, oracle, windows
    gc.collect()

    # 3. Each fight re-read and compared; one no place gives is recorded as
    # not found, with the reasons, and the log goes on
    rows = []
    for loc, zone, boss, duration_s, players, boss12, window in fights:
        start, stop, start_ms, seen, problems = ranges.get((loc.session_epoch_ms, loc.start_ms),
                                                           (None,) * 4 + (["no range"],))
        result = getattr(window, "result", {"error": "no window"})
        place = fr.Place(Path(log), "split", None, 0)
        times, reasons = [], []
        try:
            for _round in range(3 if boss12 else 1):
                began = time.perf_counter()
                states = fr.read_fight(loc, [place])
                times.append(time.perf_counter() - began)
        except fr.NotOnDisk as exc:
            states, reasons = None, reasons_of(exc)
        read = states is not None
        read_s = min(times) if read else None
        found_here = any(os.path.samefile(p.path, log) for p in fr.places_for(
            loc, split_dir=os.path.dirname(log)) if p.path.exists())
        expected = result.get("expected", {})
        got = columns_of(states, fr) if read else {}
        equal = differ = extra = 0
        details = []
        for key, cols in got.items():
            want = expected.get(key)
            if want is None:
                extra += 1
                details.append({"key": str(key)[:40], "why": "no expected track"})
            elif want == cols:
                equal += 1
            else:
                differ += 1
                unit = loc.units[key] if isinstance(key, int) else None
                details.append({"kind": unit.kind if unit else "unknown",
                                "why": "columns " + ",".join(
                                    name for (name, _c), a, b in zip(fr.STATE_COLUMNS, want, cols)
                                    if a != b),
                                "expected": len(want[0]) // 4, "reread": len(cols[0]) // 4})
        missing = sum(1 for key, cols in expected.items()
                      if key not in got and cols is not None and cols[0])
        frames_ok = read and window is not None and tuple(window.frames) == states.frames
        scan_ok = None
        scan_s = None
        scan_reasons = []
        if read and loc.begin_offset is not None:
            spoiled = loc._replace(
                begin_offset=loc.begin_offset + SPOIL,
                zone_offset=None if loc.zone_offset is None else loc.zone_offset + SPOIL)
            began = time.perf_counter()
            try:
                by_scan = fr.read_fight(spoiled, [place])
            except fr.NotOnDisk as exc:
                scan_ok, scan_reasons = False, reasons_of(exc)
            else:
                scan_s = time.perf_counter() - began
                scan_ok = by_scan.found_by == "scan" and same_read(by_scan, states, fr)
        rows.append({
            "zone": zone, "boss": boss, "duration_s": duration_s,
            "players": players, "boss12": boss12,
            "start_ms": loc.start_ms, "end_ms": loc.end_ms, "no_begin":
                loc.begin_offset is None, "problems": problems,
            "found_by": states.found_by if read else "not found", "reasons": reasons,
            "found_by_stamp": found_here,
            "range_start_ok": read and states.range_start_ms == start_ms,
            "tail_seen": read and states.tail_seen,
            "tail_seen_ok": read and states.tail_seen == seen,
            "frames": len(states.frames) if read else 0,
            "frames_ok": frames_ok, "range_bytes": (stop - start) if start is not None else None,
            "lead_bytes": (loc.begin_offset + loc.session_offset - start)
                if start is not None and loc.begin_offset is not None else None,
            "read_s": read_s, "scan_s": scan_s, "scan_ok": scan_ok,
            "scan_reasons": scan_reasons, "lines": states.lines if read else 0,
            "skipped": states.skipped if read else 0,
            "states": states.state_count if read else 0,
            "tracks": len(states.tracks) if read else 0,
            "unknown_tracks": sum(1 for t in states.tracks if t.unit is None) if read else 0,
            "table_rows": len(loc.units), "result_bytes": states.nbytes() if read else 0,
            "tracks_equal": equal, "tracks_differ": differ, "tracks_extra": extra,
            "tracks_missing": missing, "details": details[:6],
            "collisions": result.get("collisions"), "error": result.get("error"),
            "occurrences": result.get("agree", 0) + sum(result.get("causes", {}).values()),
            "agree": result.get("agree", 0), "causes": dict(result.get("causes", {})),
            "owner_bad": dict(result.get("owner_bad", {})),
            "windows": dict(result.get("windows", {})),
            "unmapped_rows": result.get("unmapped_rows"),
            "locators_equal": loc == first_locators.get((loc.session_epoch_ms, loc.start_ms)),
        })
        stats["fights"] += 1

    # 4. The split zipped as retention zips it
    zipped = None
    if zip_dir is not None:
        os.makedirs(zip_dir, exist_ok=True)
        copy = Path(shutil.copy(log, Path(zip_dir) / os.path.basename(log)))
        result = split_retention.zip_split(copy)
        target = Path(str(copy) + ".zip")
        zipped = {"zip": result.kind, "fights": 0, "equal": 0, "scan_fights": 0,
                  "scan_equal": 0, "read_s": [], "scan_s": [], "not_found": []}
        try:
            for (loc, *_about), row in zip(fights, rows):
                if row["found_by"] == "not found":
                    continue  # not read from the plain split either
                place = fr.Place(target, "split", None, 0)
                plain = fr.read_fight(loc, [fr.Place(Path(log), "split", None, 0)])
                zipped["fights"] += 1
                began = time.perf_counter()
                try:
                    from_zip = fr.read_fight(loc, [place])
                except fr.NotOnDisk as exc:
                    zipped["not_found"].append([loc.start_ms, "offset", reasons_of(exc)])
                else:
                    zipped["read_s"].append((row["boss12"], time.perf_counter() - began))
                    zipped["equal"] += (from_zip.found_by == "offset"
                                        and same_read(from_zip, plain, fr))
                if loc.begin_offset is not None:
                    spoiled = loc._replace(
                        begin_offset=loc.begin_offset + SPOIL,
                        zone_offset=None if loc.zone_offset is None else loc.zone_offset + SPOIL)
                    zipped["scan_fights"] += 1
                    began = time.perf_counter()
                    try:
                        by_scan = fr.read_fight(spoiled, [place])
                    except fr.NotOnDisk as exc:
                        zipped["not_found"].append([loc.start_ms, "time", reasons_of(exc)])
                        continue
                    zipped["scan_s"].append((row["boss12"], time.perf_counter() - began))
                    zipped["scan_equal"] += (by_scan.found_by == "scan"
                                             and same_read(by_scan, plain, fr))
        finally:
            for leftover in (target, copy):
                if leftover.exists():
                    leftover.unlink()
    result = {"log": os.path.basename(log), "bytes": os.path.getsize(log),
              "replay_s": [replay1_s, replay2_s], "rejected": dict(rejected),
              "fights": rows, "zip": zipped, "stats": dict(stats)}
    with open(out_json, "w", encoding="utf-8") as handle:
        json.dump(result, handle, default=str)


# --------------------------------------------------------------- summary --

def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, round(q * (len(values) - 1)))] if values else float("nan")


def summarize(out_dir, names=None, failed=()):
    """summary.txt from the check-<log name>.json of each of *names* (every
    one in *out_dir* when None), naming each log whose check failed:
    *failed* holds (name, exit code) for each worker that exited with an
    error, and a log that left no JSON is named too."""
    if names is None:
        names = [path.stem[len("check-"):]
                 for path in sorted(Path(out_dir).glob("check-*.json"))]
    exits = dict(failed)
    results, no_json = [], []
    for name in names:
        path = Path(out_dir, f"check-{name}.json")
        if path.exists():
            results.append(json.loads(path.read_text(encoding="utf-8")))
        elif name not in exits:
            no_json.append(name)
    fights = [dict(f, log=r["log"]) for r in results for f in r["fights"]]
    out = []
    say = out.append
    total = sum(r["bytes"] for r in results)
    say(f"{len(results)} logs, {total / 1048576:.0f} MB, {len(fights)} fights; engine replays "
        f"{sum(r['replay_s'][0] for r in results):.0f} s plain, "
        f"{sum(r['replay_s'][1] for r in results):.0f} s with the oracle")
    if exits or no_json:
        say(f"{len(exits) + len(no_json)} of {len(names)} logs failed, not in the totals: "
            + "; ".join([f"{name} exit {code} (see run-{name}.txt)" for name, code in failed]
                        + [f"{name} wrote no check-{name}.json" for name in no_json]))
    say(f"rejected by the parser (all lines): {dict(sum((Counter(r['rejected']) for r in results), Counter()))}")
    say(f"locator problems: {Counter(p for f in fights for p in f['problems'])}; "
        f"oracle errors {Counter(f['error'] for f in fights if f['error'])}; "
        f"locators equal across the replays {sum(f['locators_equal'] for f in fights)}")
    say(f"found by {dict(Counter(f['found_by'] for f in fights))}; split found by its stamp "
        f"{sum(f['found_by_stamp'] for f in fights)}; range start right "
        f"{sum(f['range_start_ok'] for f in fights)}; tail seen {sum(f['tail_seen'] for f in fights)}"
        f" (as the oracle {sum(f['tail_seen_ok'] for f in fights)}); frames right "
        f"{sum(f['frames_ok'] for f in fights)}; skipped lines {sum(f['skipped'] for f in fights)}")
    lost = [f for f in fights if f["found_by"] == "not found"]
    if lost:
        say(f"not found: {len(lost)} fights, why "
            f"{dict(Counter(why.split(': ', 1)[-1] for f in lost for why in f['reasons']))}")
        for f in lost[:15]:
            say(f"  {Path(f['log']).stem} {f['zone']} / {f['boss']} at {f['start_ms']} ms: "
                f"{f['reasons']}")
    say(f"spoiled offsets: found by time and identical {sum(1 for f in fights if f['scan_ok'])} "
        f"of {sum(1 for f in fights if f['scan_ok'] is not None)}; not found "
        f"{sum(1 for f in fights if f.get('scan_reasons'))}")
    say(f"tracks: equal {sum(f['tracks_equal'] for f in fights)}, differ "
        f"{sum(f['tracks_differ'] for f in fights)}, re-read with no expected "
        f"{sum(f['tracks_extra'] for f in fights)}, expected not re-read "
        f"{sum(f['tracks_missing'] for f in fights)}, engine keys sharing a table key "
        f"{sum(f['collisions'] or 0 for f in fights)}; rows not mapped to the engine "
        f"{sum(f['unmapped_rows'] or 0 for f in fights)}")
    for f in [f for f in fights if f["tracks_differ"] or f["tracks_extra"]][:15]:
        say(f"  {Path(f['log']).stem} {f['zone']} / {f['boss']} {f['duration_s']:.0f} s: "
            f"{f['details'][:3]}")
    occ = sum(f["occurrences"] for f in fights)
    agree = sum(f["agree"] for f in fights)
    causes = sum((Counter(f["causes"]) for f in fights), Counter())
    owners = sum((Counter(f["owner_bad"]) for f in fights), Counter())
    say(f"identity of {occ} state occurrences: the unit agrees in {agree} ({agree / max(occ, 1):.4%});"
        f" differs by cause {dict(causes)} in {sum(1 for f in fights if f['causes'])} fights")
    say(f"owner differs {dict(owners)} ({sum(owners.values()) / max(occ, 1):.4%}) in "
        f"{sum(1 for f in fights if f['owner_bad'])} fights")
    windows = sum((Counter(f.get("windows", {})) for f in fights), Counter())
    say(f"windows: {dict(windows)}; fights with an id two rows name "
        f"{sum(1 for f in fights if f.get('windows', {}).get('on an id two or more rows name'))}")
    for label, chosen in (("12-player boss fights", [f for f in fights if f["boss12"]]),
                          ("all fights", fights)):
        if not chosen:
            continue
        say(f"\n{label}: {len(chosen)}")
        for key, scale, unit in (("duration_s", 1, "s"), ("range_bytes", 1 / 1048576, "MB"),
                                 ("lead_bytes", 1 / 1024, "KB lead"), ("read_s", 1000, "ms"),
                                 ("scan_s", 1000, "ms scan"), ("states", 1, "states"),
                                 ("tracks", 1, "tracks"), ("unknown_tracks", 1, "unknown"),
                                 ("result_bytes", 1 / 1024, "KB result")):
            values = [f[key] * scale for f in chosen if f[key] is not None]
            if values:
                say(f"  {unit:10s} median {pct(values, 0.5):10.2f}  p90 {pct(values, 0.9):10.2f}  "
                    f"max {max(values):10.2f}")
        states = sum(f["states"] for f in chosen)
        timed = [f for f in chosen if f["read_s"] is not None]   # the fights found
        read_s = sum(f["read_s"] for f in timed)
        say(f"  {sum(f['result_bytes'] for f in chosen) / max(states, 1):.1f} result bytes a state"
            + (f"; {sum(f['range_bytes'] or 0 for f in timed) / 1048576 / read_s:.0f} MB/s"
               if read_s else ""))
        if timed:
            worst = max(timed, key=lambda f: f["read_s"])
            say(f"  slowest: {worst['zone']} / {worst['boss']} {worst['duration_s']:.0f} s, "
                f"{(worst['range_bytes'] or 0) / 1048576:.1f} MB, {worst['read_s'] * 1000:.0f} ms")
    for r in results:
        z = r.get("zip")
        if z:
            reads = [s for _b, s in z["read_s"]]
            scans = [s for _b, s in z["scan_s"]]
            boss_read = [s for b, s in z["read_s"] if b]
            say(f"\nzip {Path(r['log']).stem}: {z['zip']}; {z['equal']} of {z['fights']} equal by"
                f" offset, {z['scan_equal']} of {z.get('scan_fights', len(scans))} by time"
                + (f"; not found {z['not_found']}" if z.get("not_found") else "")
                + (f"; read median {pct(reads, 0.5) * 1000:.0f} ms, max {max(reads) * 1000:.0f} ms"
                   if reads else "")
                + (f"; 12-player boss median {pct(boss_read, 0.5) * 1000:.0f} ms" if boss_read
                   else "")
                + (f"; by time median {pct(scans, 0.5) * 1000:.0f} ms, max "
                   f"{max(scans) * 1000:.0f} ms" if scans else ""))
    text = "\n".join(out)
    Path(out_dir, "summary.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


# ------------------------------------------------------------------ main --

def logs_from(items):
    logs = []
    for item in items:
        if item.lower().endswith(".tsv"):
            with open(item, encoding="utf-8") as handle:
                logs += [line.rstrip("\n").split("\t")[-1] for line in handle
                         if line.strip() and not line.startswith("#")]
        else:
            logs.append(item)
    return logs


def main():
    if sys.argv[1:2] == ["--worker"]:
        src, log, out_json, zip_dir = sys.argv[2:6]
        check_log(src, log, out_json, zip_dir or None)
        return
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("src")
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--zip", action="append", default=[], metavar="STAMP")
    parser.add_argument("--zip-dir")
    args = parser.parse_args()
    *items, out_dir = args.logs
    logs = sorted(logs_from(items), key=lambda path: -os.path.getsize(path))
    # The outputs are named by the log's whole file name: several splits
    # share a session's stamp, and one log's output must not overwrite
    # another's
    names = [Path(log).stem for log in logs]
    clash = sorted(name for name, count in Counter(names).items() if count > 1)
    if clash:
        parser.error(f"logs with the same file name, whose outputs would overwrite each "
                     f"other's: {', '.join(clash)}")
    os.makedirs(out_dir, exist_ok=True)

    def one(log):
        name = Path(log).stem
        stamp = os.path.basename(log)[:12]
        out_json = os.path.join(out_dir, f"check-{name}.json")
        if os.path.exists(out_json):
            os.remove(out_json)   # a last run's, which a failed worker would leave
        zip_dir = (args.zip_dir or os.path.join(out_dir, "zips")) if stamp in args.zip else ""
        with open(os.path.join(out_dir, f"run-{name}.txt"), "w", encoding="utf-8") as errors:
            done = subprocess.run([sys.executable, "-X", "utf8", "-B", os.path.abspath(__file__),
                                   "--worker", args.src, log, out_json, zip_dir],
                                  stdout=subprocess.DEVNULL, stderr=errors, check=False)
        return name, done.returncode

    failed = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 6))) as pool:
        for name, code in pool.map(one, logs):
            print(f"{name} {'ok' if code == 0 else f'exit {code}'}", flush=True)
            if code:
                failed.append((name, code))
    summarize(out_dir, names, failed)


if __name__ == "__main__":
    main()
