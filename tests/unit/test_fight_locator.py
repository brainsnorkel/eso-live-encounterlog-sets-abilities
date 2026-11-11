#!/usr/bin/env python3
"""Where a fight's lines are in its log and who its units are (issue #214),
tested from the design (fight_locator's module notes) rather than from the
code: the locator every fight's entry carries, and the byte readers that
say where each line starts.

What the design asks for, and these tests pin:

- Offsets are bytes counted from the first byte of the session's BEGIN_LOG
  line, the same number in the live log, in the session's split and in a
  zipped split's member; the BEGIN_LOG line's own offset in the file read
  and its Unix ms name the session.
- Every reader that feeds the engine reads bytes and says where each line
  starts: the live tail, the attach (and Settings-save) replay, the review
  of a plain or a zipped log, and the roster sweep. A line the game has not
  finished writing is read once, whole, when it is; a line the engine
  raises on is passed once, and the lines before it are not read again.
- start_ms and end_ms are the BEGIN_COMBAT and END_COMBAT lines' times,
  whatever moves the encounter's start later; a fight the game cut in two
  keeps its first BEGIN_COMBAT and takes its last END_COMBAT.
- The map in force as the 10 s lead-in begins; the zone's maps and units
  are the zone's own.
- The unit table is the engine's identity of the fight's units, frozen as
  the entry is built.

Every log here is written as bytes with its line ends spelled out, CRLF as
the game writes or LF, and every expected offset is taken from those
bytes: the golden fixture is LF in git and CRLF only through autocrlf on
Windows, so no offset here comes from it. Names carry 2-, 3- and 4-byte
UTF-8 characters, where characters and bytes part ways. All names and
handles are made up.
"""

import copy
import json
import zipfile
from itertools import pairwise
from pathlib import Path

import pytest

import companions
import fight_locator
import fight_opener
import fight_reread
import review_load
import split_retention
from engine_events import RecordingListener
from esolog_tail import (
    LATE_DEATH_GRACE_MS,
    ESOLogAnalyzer,
    FightHistory,
    LogFileMonitor,
    find_session_start_offset,
)
from fight_history import FightHistoryEntry
from fight_locator import LEAD_MS, MAPS_KEPT, TAIL_MS, MapFrame, map_before
from log_open import open_log_bytes
from waiting_hits import FIGHT_ON_MS

EPOCH = 1793600000000          # a session's BEGIN_LOG, Unix ms
OTHER_EPOCH = EPOCH + 3_600_000
CRLF, LF = b"\r\n", b"\n"
MIB = 1 << 20
BOSS_HEALTH = 1_000_000
TRASH_HEALTH = 1_000_000
STRIKE = 12345                 # the group's skill
GRACE = 45549                  # a passive the builds list
UNBOUND_POTENTIAL = 263411     # an Arcanist's mastery, known only when it fires
ISOBEL, MIRRI = "106616", "103089"   # companions' monster ids
SEA_ADDER = "96308"            # boss-flagged, not a boss (boss_units)

MAP_EARLY = MapFrame("2110", "Brackish Cove", "summerset/CoralAerie_Beach_001")
MAP_LEAD = MapFrame("2111", "Côte Sombre", "summerset/CoralAerie_Cove_002")
MAP_FIGHT = MapFrame("2112", "Tiefe Grötte", "summerset/CoralAerie_Grotto_003")
MAP_EDGE = MapFrame("2113", "珊瑚の間", "summerset/CoralAerie_Hall_004")

# Lines the parser rejects; a split since 0.19.0 keeps them
OBJECT_LINE = '2500,UNIT_ADDED,95,OBJECT,F,0,0,F,0,0,"Brimstone Anchor","",0,0,0,0,NPC_NEUTRAL,F'
CANCELLED_CAST = "27000,END_CAST,PLAYER_CANCELLED,7883445,269230"


# ------------------------------------------------------------------ lines --

def state(unit, health=20000):
    """A player's unit state."""
    return f"{unit},{health}/20000,26657/26657,13021/13021,500/500,1000/1000,0,0.2,0.5,5.5"


def mob(unit, health, maximum=BOSS_HEALTH):
    """A monster's unit state."""
    return f"{unit},{health}/{maximum},0/0,0/0,0/0,0/0,0,0.6,0.4,2.3"


def companion_state(unit, health=33000):
    return f"{unit},{health}/33000,0/0,0/0,0/0,0/0,0,0.3,0.4,1.0"


TRAP = mob(81, 0, 0)  # a neutral trap: no enemy


def hit(ts, source, target, damage=50000, result="DAMAGE", ability=STRIKE):
    return (f"{ts},COMBAT_EVENT,{result},PHYSICAL,1,{damage},0,{ts},{ability},"
            f"{source},{target}")


def player_hits(ts, player, target, damage=50000):
    return hit(ts, state(player), target, damage)


def died(ts, killer, player):
    return f"{ts},COMBAT_EVENT,DIED,PHYSICAL,1,0,0,{ts},{STRIKE},{killer},{state(player, 0)}"


def begin_log(epoch, t=3):
    """A BEGIN_LOG with a one-digit time field, as the game writes them."""
    return f'{t},BEGIN_LOG,{epoch},15,"NA Megaserver","en","eso.live.12.1"'


def zone_changed(t, zone_id=1344, name="Dreadsail Reef", difficulty="VETERAN"):
    return f'{t},ZONE_CHANGED,{zone_id},"{name}",{difficulty}'


def map_changed(t, frame):
    return f'{t},MAP_CHANGED,{frame.map_id},"{frame.name}","{frame.texture}"'


def player_added(ts, unit, name, handle, character, class_id=6, local="F", grouped="T"):
    return (f'{ts},UNIT_ADDED,{unit},PLAYER,{local},{unit},0,F,{class_id},1,"{name}",'
            f'"{handle}",{character},50,2547,0,PLAYER_ALLY,{grouped}')


def monster_added(ts, unit, name, monster_id, boss="F", reaction="HOSTILE", owner=0):
    return (f'{ts},UNIT_ADDED,{unit},MONSTER,F,0,{monster_id},{boss},0,0,"{name}","",0,50,160,'
            f'{owner},{reaction},F')


def companion_added(ts, unit, owner, reaction="COMPANION", monster=ISOBEL,
                    name="Isobel Veloise"):
    return (f'{ts},UNIT_ADDED,{unit},MONSTER,F,0,{monster},F,0,0,"{name}","",0,20,0,'
            f'{owner},{reaction},F')


def unit_changed(ts, unit, name, owner, reaction):
    return f'{ts},UNIT_CHANGED,{unit},0,0,"{name}","",0,50,0,{owner},{reaction},F'


def removed(ts, unit):
    return f"{ts},UNIT_REMOVED,{unit}"


def builds(ts, *players):
    """The PLAYER_INFO lines the game writes after each BEGIN_COMBAT."""
    return [f"{ts},PLAYER_INFO,{unit},[{GRACE}],[1],[],[{STRIKE}],[{STRIKE}]" for unit in players]


def self_effect(ts, player):
    """A self-targeted line: its last field is '*'."""
    return f"{ts},EFFECT_CHANGED,GAINED,1,777,{GRACE},{state(player)},*"


def gained(ts, ability, player):
    return f"{ts},EFFECT_CHANGED,GAINED,1,778,{ability},{state(player)},*"


def regen(ts, player=1):
    """A line with nothing in it for any fight: the log goes on."""
    return f"{ts},HEALTH_REGEN,50,{state(player)}"


def fight(begin, end, *lines, players=(1, 2, 3)):
    return [f"{begin},BEGIN_COMBAT", *builds(begin + 1, *players), *lines, f"{end},END_COMBAT"]


ABILITIES = [
    f'2600,ABILITY_INFO,{STRIKE},"Damage Ability","/esoui/art/icons/ability_weapon_001.dds",F,F',
    f'2600,ABILITY_INFO,{GRACE},"Grace","/esoui/art/icons/ability_armor_004.dds",T,T',
    (f'2600,ABILITY_INFO,{UNBOUND_POTENTIAL},"Unbound Potential",'
     f'"/esoui/art/icons/passive_arcanist_04.dds",F,F'),
]

FIRST = (20000, 40000)    # the session's boss fight: BEGIN_COMBAT, END_COMBAT
SECOND = (60000, 70000)   # and its trash fight


def session(epoch=EPOCH, blanks=True):
    """A Dreadsail Reef session of two fights, the boss from 20 s to 40 s
    and a trash pack from 60 s to 70 s. Maps change 15 s and 3 s before the
    first BEGIN_COMBAT, inside the first fight, and exactly as the second
    fight's lead-in begins; an OBJECT unit and a cancelled cast the parser
    rejects; and, with *blanks*, an empty line and a line of spaces, which
    the corpus never has but whose bytes still count."""
    return [
        begin_log(epoch),
        zone_changed(3),
        player_added(2000, 1, "Zoë Testé", "@tëster", 1001, class_id=117, local="T"),
        player_added(2000, 2, "Björn Ödegård", "@björn", 1002),
        player_added(2000, 3, "テスト太郎", "@テスト", 1003, grouped="F"),
        player_added(2000, 4, "Drache 𝔘🐉", "@drache", 1004),
        monster_added(2500, 70, "Tideborn Taleria", BOSS_HEALTH, boss="T"),
        monster_added(2500, 71, "Dreadsail Deckhand", TRASH_HEALTH),
        OBJECT_LINE,
        *(["", "   "] if blanks else []),
        *ABILITIES,
        map_changed(5000, MAP_EARLY),
        map_changed(17000, MAP_LEAD),
        *fight(20000, 40000,
               player_hits(21000, 1, mob(70, 950000)),
               self_effect(21500, 1),
               map_changed(25000, MAP_FIGHT),
               player_hits(26000, 2, mob(70, 900000)),
               CANCELLED_CAST,
               player_hits(29000, 3, mob(70, 850000)),
               player_hits(29500, 4, mob(70, 800000)),
               players=(1, 2, 3, 4)),
        map_changed(50000, MAP_EDGE),
        *fight(60000, 70000,
               player_hits(61000, 4, mob(71, 950000, TRASH_HEALTH)),
               player_hits(65000, 1, mob(71, 900000, TRASH_HEALTH)),
               players=(1, 2, 3, 4)),
        regen(90000),
        "95000,END_LOG",
    ]


def base(epoch=EPOCH):
    """A session's head: the zone, three grouped players (the logging one
    an Arcanist), a boss, a trash monster and an add."""
    return [
        begin_log(epoch),
        zone_changed(1000),
        player_added(2000, 1, "Zoë Testé", "@tëster", 1001, class_id=117, local="T"),
        player_added(2000, 2, "Björn Ödegård", "@björn", 1002),
        player_added(2000, 3, "テスト太郎", "@テスト", 1003),
        monster_added(2500, 70, "Tideborn Taleria", BOSS_HEALTH, boss="T"),
        monster_added(2500, 71, "Dreadsail Deckhand", TRASH_HEALTH),
        monster_added(2500, 72, "Sea Adder Spawn", 50000),
        *ABILITIES,
    ]


def trash(health):
    return mob(71, health, TRASH_HEALTH)


# ------------------------------------------------------------------- logs --

class Written:
    """A log as the test writes it: its lines, their bytes with *newline*,
    and the offset at which each line begins."""

    def __init__(self, lines, newline=CRLF):
        self.lines = list(lines)
        self.newline = newline
        self.raw = [line.encode("utf-8") + newline for line in self.lines]
        self.data = b"".join(self.raw)
        self.starts = []
        at = 0
        for raw in self.raw:
            self.starts.append(at)
            at += len(raw)

    def at(self, line, after=0):
        """The offset of the first *line* at or after line index *after*."""
        return self.starts[self.lines.index(line, after)]

    def sessions(self):
        """The line index of each BEGIN_LOG."""
        return [i for i, line in enumerate(self.lines) if ",BEGIN_LOG," in line]

    def engine_lines(self):
        """(offset, line) of every line the parser takes, in order: what the
        engine must be handed, each line once, whole, at its first byte."""
        parse = ESOLogAnalyzer().log_parser.parse_line
        return [(start, line.strip()) for start, line in zip(self.starts, self.lines)
                if line.strip() and parse(line.strip()) is not None]


def line_at(data, offset):
    """The line beginning at *offset*, without its line end; None when
    *offset* is not the first byte of a line."""
    if offset is None or not 0 <= offset < len(data):
        return None
    if offset and data[offset - 1:offset] != b"\n":
        return None
    end = data.find(b"\n", offset)
    return data[offset:end if end != -1 else len(data)].rstrip(b"\r")


def placed(log, start_ms, end_ms, map_at_lead, session_index=0):
    """What the locator of the fight from *start_ms* to *end_ms* in the
    *session_index*-th session of *log* must hold, all but its units: the
    session's stamp, Unix ms and offset, and the zone line's, the
    BEGIN_COMBAT line's and the END_COMBAT line's offsets from it."""
    first = log.sessions()[session_index]
    epoch = int(log.lines[first].split(",")[2])
    base_offset = log.starts[first]
    zone = next(i for i in range(first, len(log.lines)) if ",ZONE_CHANGED," in log.lines[i])
    return (split_retention.session_stamp(epoch), epoch, base_offset,
            log.starts[zone] - base_offset,
            log.at(f"{start_ms},BEGIN_COMBAT", first) - base_offset,
            log.at(f"{end_ms},END_COMBAT", first) - base_offset,
            start_ms, end_ms, map_at_lead)


def assert_on_its_lines(data, locator):
    """The re-reader's checks on open (fight_locator): the line at the
    session's offset is a BEGIN_LOG with the session's Unix ms, and the
    lines at its offsets are the fight's BEGIN_COMBAT, END_COMBAT and zone
    lines, each at a line's first byte."""
    session_offset = locator.session_offset
    head = line_at(data, session_offset)
    assert head is not None and head.split(b",")[1] == b"BEGIN_LOG", head
    assert int(head.split(b",")[2]) == locator.session_epoch_ms
    assert (line_at(data, session_offset + locator.begin_offset)
            == f"{locator.start_ms},BEGIN_COMBAT".encode())
    assert (line_at(data, session_offset + locator.end_offset)
            == f"{locator.end_ms},END_COMBAT".encode())
    assert line_at(data, session_offset + locator.zone_offset).split(b",")[1] == b"ZONE_CHANGED"


def write(path, data):
    Path(path).write_bytes(data)
    return Path(path)


def zipped(path, member, data):
    """A log zipped as split retention zips it: one deflated member."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, data)
    return Path(path)


def cut_points(data):
    """Where a poll can land while the game writes: inside each line,
    between each CR and its LF, inside each multibyte character, and one
    byte into each BEGIN_LOG line (just after its time field)."""
    cuts = set()
    start = 0
    while start < len(data):
        end = data.index(b"\n", start) + 1
        cuts.add(start + (end - start) // 2)
        if data[end - 2:end] == CRLF:
            cuts.add(end - 1)
        if b",BEGIN_LOG," in data[start:end]:
            cuts.add(start + 1)
        start = end
    for i, byte in enumerate(data):
        if byte >= 0xC0:
            width = 2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
            cuts.update(range(i + 1, i + width))
    return sorted(cut for cut in cuts if 0 < cut < len(data))


def filler(size, t=96000):
    """Lines the parser rejects (cancelled casts), *size* bytes in all."""
    head, end = f"{t},END_CAST,PLAYER_CANCELLED,".encode(), b",1\r\n"
    smallest = len(head) + len(end) + 1
    out = []
    while size:
        n = 4000 if size >= 4000 + smallest else size
        assert n >= smallest
        out.append(head + b"9" * (n - len(head) - len(end)) + end)
        size -= n
    return b"".join(out)


# ---------------------------------------------------------------- readers --

class Engine(ESOLogAnalyzer):
    """The engine, noting each entry it is handed with the offset its
    reader set (ESOLogAnalyzer.line_offset) and the fight events it sends."""

    def __init__(self):
        super().__init__()
        self.fight_history = FightHistory()
        self.listener = RecordingListener()
        self.add_listener(self.listener)
        self.seen = []

    def process_log_entry(self, entry):
        self.seen.append((self.line_offset, entry.original_line))
        super().process_log_entry(entry)

    @property
    def fights(self):
        return self.fight_history.fights

    def updates(self, entry):
        """How many times frontends were told *entry* changed."""
        return sum(1 for event in self.listener.events
                   if event[0] == "fight_updated" and event[1] is entry)


def review(path, member=None):
    """Open log for review: review_load.replay_log over the file's bytes."""
    engine = Engine()
    _shown, fights = review_load.replay_log(engine, Path(path), member)
    assert fights == engine.fights
    return engine


def attach(path, **kwargs):
    """The app attaching to the log (or a Settings save rebuilding the
    monitor): LogFileMonitor replays the latest session."""
    engine = Engine()
    monitor = LogFileMonitor(engine, Path(path), **kwargs)
    return engine, monitor


def tail(path, data, cuts=(), **kwargs):
    """The live tail: *data* written to an empty *path* in pieces ending at
    *cuts*, the engine thread's poll after each."""
    path = write(path, b"")
    engine = Engine()
    monitor = LogFileMonitor(engine, path, **kwargs)
    done = 0
    for cut in [*cuts, len(data)]:
        with open(path, "ab") as f:
            f.write(data[done:cut])
        done = cut
        monitor._process_new_lines()
    return engine, monitor


def feed(lines, engine=None):
    """No reader at all: process_log_entry directly, as most tests and
    scripts do, so no line has an offset."""
    engine = engine or Engine()
    for line in lines:
        entry = engine.log_parser.parse_line(line)
        if entry is not None:
            engine.process_log_entry(entry)
    return engine


class LiveLog:
    """A scratch log the test writes as the game does, the live tail
    polling after each write."""

    def __init__(self, path, newline=CRLF):
        self.path = write(path, b"")
        self.newline = newline
        self.lines = []
        self.engine = Engine()
        self.monitor = LogFileMonitor(self.engine, self.path)

    def write(self, *lines):
        with open(self.path, "ab") as f:
            f.writelines(line.encode("utf-8") + self.newline for line in lines)
        self.lines.extend(lines)
        self.monitor._process_new_lines()
        return self

    @property
    def log(self):
        return Written(self.lines, self.newline)

    @property
    def fights(self):
        return self.engine.fights


def digest(entry):
    """Every slot of a fight but its wall-clock build time."""
    def plain(value):
        if isinstance(value, (set, frozenset)):
            return sorted(value, key=str)
        return str(value)
    return json.dumps({slot: getattr(entry, slot) for slot in FightHistoryEntry.__slots__
                       if slot != "ended_at"}, default=plain, sort_keys=True)


def rows(locator, key):
    """The unit table's rows of *key*, by arrival."""
    return sorted((unit for unit in locator.units if unit.key == key),
                  key=lambda unit: unit.since_ms if unit.since_ms is not None else -1)


# ------------------------------------------------------------------ tests --

def test_an_entry_has_a_locator_slot_that_starts_empty():
    assert "locator" in FightHistoryEntry.__slots__
    assert FightHistoryEntry().locator is None


def test_the_range_covers_the_openers_moments_and_the_late_death_grace():
    """LEAD_MS before BEGIN_COMBAT, the moments the opener and the waiting
    hits read; TAIL_MS after END_COMBAT, the late-death grace."""
    assert LEAD_MS == 10_000 and LEAD_MS >= fight_opener.OPENER_WINDOW_MS
    assert TAIL_MS == 1_000 and TAIL_MS >= LATE_DEATH_GRACE_MS


def test_the_map_in_force_is_the_last_written_before_the_moment():
    maps = [(5000, MAP_EARLY), (10000, MAP_LEAD), (12000, MAP_FIGHT)]
    assert map_before([], 1) is None
    assert map_before(maps, 4999) is None
    # A change at the moment itself is the range's own line, met by the reader
    assert map_before(maps, 5000) is None
    assert map_before(maps, 5001) == MAP_EARLY
    assert map_before(maps, 10000) == MAP_EARLY
    assert map_before(maps, 11999) == MAP_LEAD
    assert map_before(maps, 99999) == MAP_FIGHT


def test_the_synthetic_logs_have_what_they_claim():
    """The session's own preconditions: names in 2-, 3- and 4-byte
    characters, a line ending '*', lines the parser rejects, blank lines."""
    log = Written(session())
    assert b"\xc3" in log.data and b"\xe3" in log.data and b"\xf0" in log.data
    assert b",*\r\n" in log.data
    parse = ESOLogAnalyzer().log_parser.parse_line
    assert parse(OBJECT_LINE) is None and parse(CANCELLED_CAST) is None
    assert b"\r\n\r\n" in log.data and b"\r\n   \r\n" in log.data
    assert log.data.startswith(b"3,BEGIN_LOG,")


@pytest.fixture(params=[CRLF, LF], ids=["crlf", "lf"])
def newline(request):
    return request.param


def test_every_reader_puts_the_locator_on_its_lines(tmp_path, newline):
    """One session through the review of the plain log, the review of the
    log zipped, the attach (and a Settings save's attach again) and the
    live tail polled at every awkward byte: each gives the engine every
    line once, whole, at its offset, and each fight a locator whose offsets
    land on its session's BEGIN_LOG, its BEGIN_COMBAT and END_COMBAT lines
    and its zone line, with the map in force as its lead-in begins (the map
    3 s before the first BEGIN_COMBAT is inside the lead-in, and the one
    written exactly as the second fight's lead-in begins is its own line).
    The readers give equal locators and the same fights. An LF log's
    offsets are its own bytes'."""
    log = Written(session(), newline)
    plain = write(tmp_path / "Encounter.log", log.data)
    engines = {
        "review": review(plain),
        "zip": review(zipped(tmp_path / "split.log.zip", "split.log", log.data)),
        "attach": attach(plain)[0],
        "attach again": attach(plain)[0],
        "tail": tail(tmp_path / "Tailed.log", log.data, cut_points(log.data))[0],
    }
    expected = [placed(log, *FIRST, MAP_EARLY), placed(log, *SECOND, MAP_FIGHT)]
    lines = log.engine_lines()
    reference = engines["review"]
    for name, engine in engines.items():
        assert engine.seen == lines, name
        assert [tuple(f.locator[:9]) for f in engine.fights] == expected, name
        for entry in engine.fights:
            assert_on_its_lines(log.data, entry.locator)
        assert [f.locator for f in engine.fights] == [f.locator for f in reference.fights], name
        assert [digest(f) for f in engine.fights] == [digest(f) for f in reference.fights], name
    # Immutable through and through (handed whole to a reader thread, and
    # compared by value after a deepcopy), so hashable
    for entry in reference.fights:
        hash(entry.locator)
        assert copy.deepcopy(entry.locator) == entry.locator
    # The units are filled: the four players by kind, the boss
    units = {(unit.key, unit.kind) for unit in reference.fights[0].locator.units}
    assert units == {("1", fight_locator.SELF), ("2", fight_locator.GROUP),
                     ("3", fight_locator.PLAYER), ("4", fight_locator.GROUP),
                     ("70", fight_locator.BOSS), ("71", fight_locator.ENEMY)}


def test_an_lf_log_counts_its_own_bytes(tmp_path):
    """Characters are not bytes and an LF log is not a CRLF one: the same
    lines put the fight at different offsets, each its file's own."""
    crlf, lf = Written(session(), CRLF), Written(session(), LF)
    from_crlf = review(write(tmp_path / "crlf.log", crlf.data)).fights[0].locator
    from_lf = review(write(tmp_path / "lf.log", lf.data)).fights[0].locator
    assert from_lf.begin_offset == lf.at("20000,BEGIN_COMBAT")
    assert from_crlf.begin_offset == crlf.at("20000,BEGIN_COMBAT")
    assert from_crlf.begin_offset - from_lf.begin_offset == crlf.lines.index("20000,BEGIN_COMBAT")
    # What text mode counts (characters, a CRLF read as one) is neither
    text = lf.data.decode("utf-8")
    characters = len(text[:text.index("20000,BEGIN_COMBAT")])
    assert characters < from_lf.begin_offset < from_crlf.begin_offset


def test_a_second_session_counts_from_its_own_begin_log(tmp_path):
    """A live log of two sessions: the second's offsets from its BEGIN_LOG
    are the session's alone (its split's), its BEGIN_LOG at the first
    session's size; an attach replays the second session alone and places
    it the same."""
    first, second = session(EPOCH), session(OTHER_EPOCH)
    alone, both = Written(second), Written(first + second)
    size = len(Written(first).data)
    alone_fights = review(write(tmp_path / "split.log", alone.data)).fights
    both_engine = review(write(tmp_path / "Encounter.log", both.data))
    assert len(both_engine.fights) == 4
    assert [f.locator.session_offset for f in both_engine.fights] == [0, 0, size, size]
    for got, own in zip(both_engine.fights[2:], alone_fights, strict=True):
        assert got.locator == own.locator._replace(session_offset=size)
        assert_on_its_lines(both.data, got.locator)
        # The relative offsets land in the session alone
        assert_on_its_lines(alone.data, got.locator._replace(session_offset=0))
    assert ([tuple(f.locator[:9]) for f in both_engine.fights[2:]]
            == [placed(both, *FIRST, MAP_EARLY, 1), placed(both, *SECOND, MAP_FIGHT, 1)])
    engine, monitor = attach(tmp_path / "Encounter.log")
    assert [f.locator for f in engine.fights] == [f.locator for f in both_engine.fights[2:]]
    assert monitor.last_position == len(both.data)
    # A review of the second session alone (Outline.begin_log) counts the
    # bytes it skips: offsets in the file, as the whole review's
    later = Engine()
    _shown, fights = review_load.replay_log(later, tmp_path / "Encounter.log", from_begin_log=1)
    assert [f.locator for f in fights] == [f.locator for f in both_engine.fights[2:]]


def _cut(log, where):
    """A byte position inside a line of the session, and that line's
    first byte."""
    if where == "inside a hit":
        line = player_hits(26000, 2, mob(70, 900000))
        start = log.at(line)
        return start + len(line) // 2, start
    if where == "between CR and LF":
        start = log.at("40000,END_COMBAT")
        return start + len(b"40000,END_COMBAT\r"), start
    if where == "inside a 4-byte character":
        line = next(line for line in log.lines if "🐉" in line)
        start = log.at(line)
        return start + line.encode("utf-8").index("🐉".encode()) + 2, start
    raise ValueError(where)


@pytest.mark.parametrize("where", ["inside a hit", "between CR and LF",
                                   "inside a 4-byte character"])
def test_an_attach_while_the_game_writes_reads_the_line_once_whole(tmp_path, where):
    """The game is writing a line as the app attaches: the replay leaves
    the line it has no newline for, the tail starts at its first byte, and
    the next poll reads it once, whole, the tail ending at the file's
    size."""
    log = Written(session())
    cut, line_start = _cut(log, where)
    path = write(tmp_path / "Encounter.log", log.data[:cut])
    engine, monitor = attach(path)
    assert engine.seen == [(at, line) for at, line in log.engine_lines() if at < line_start]
    assert monitor.last_position == line_start
    with open(path, "ab") as f:
        f.write(log.data[cut:])
    monitor._process_new_lines()
    assert engine.seen == log.engine_lines()
    assert monitor.last_position == len(log.data)
    whole = review(write(tmp_path / "whole.log", log.data))
    assert [f.locator for f in engine.fights] == [f.locator for f in whole.fights]
    assert [digest(f) for f in engine.fights] == [digest(f) for f in whole.fights]


@pytest.mark.parametrize("where", ["inside a hit", "between CR and LF",
                                   "inside a 4-byte character"])
def test_a_poll_inside_a_line_reads_it_whole_at_the_next(tmp_path, where):
    """The live tail's poll lands inside a line: nothing of it is read
    until the next poll, which reads it once, whole (read as text, the
    tail once handed the parser two broken pieces and lost a fight)."""
    log = Written(session())
    cut, line_start = _cut(log, where)
    engine, monitor = tail(tmp_path / "Encounter.log", log.data[:cut])
    assert engine.seen == [(at, line) for at, line in log.engine_lines() if at < line_start]
    assert monitor.last_position == line_start
    with open(monitor.log_file, "ab") as f:
        f.write(log.data[cut:])
    monitor._process_new_lines()
    assert engine.seen == log.engine_lines()
    assert monitor.last_position == len(log.data)
    assert [tuple(f.locator[:9]) for f in engine.fights] == [
        placed(log, *FIRST, MAP_EARLY), placed(log, *SECOND, MAP_FIGHT)]


def _boundary_log():
    """A log whose second session's BEGIN_LOG begins at *s*, with exactly
    1 MiB + 1 bytes from it to the file's end: the BEGIN_LOG search's first
    1 MiB chunk then begins one byte into that line, just after its
    one-digit time field."""
    head = Written(session(EPOCH)).data
    body = Written(session(OTHER_EPOCH)).data
    s = len(head)
    data = head + body + filler(1 + MIB - len(body))
    assert len(data) == s + 1 + MIB and data[s:s + 2] == b"3,"
    return data, s


def test_the_session_start_when_a_chunk_boundary_falls_one_byte_into_it(tmp_path):
    data, s = _boundary_log()
    path = write(tmp_path / "Encounter.log", data)
    assert find_session_start_offset(path, len(data), 2 << 30) == s
    longer = write(tmp_path / "longer.log", data + filler(8192, t=97000))
    for end in (s + MIB, s + 1 + MIB, s + 2 + MIB, s + 12 + MIB, len(data) + 8192):
        assert find_session_start_offset(longer, end, 2 << 30) == s, end


def test_an_attach_at_that_boundary_replays_the_session_from_its_begin_log(tmp_path):
    data, s = _boundary_log()
    engine, monitor = attach(write(tmp_path / "Encounter.log", data))
    assert engine.seen[0] == (s, begin_log(OTHER_EPOCH))
    assert engine.session_offset == s and engine.session_epoch_ms == OTHER_EPOCH
    assert [f.locator.session_offset for f in engine.fights] == [s, s]
    for entry in engine.fights:
        assert_on_its_lines(data, entry.locator)
        assert entry.session_stamp == split_retention.session_stamp(OTHER_EPOCH)
    assert monitor.last_position == len(data)


def test_a_cancelled_poll_resumes_at_the_first_line_not_read(tmp_path):
    """The tail's cancel (polled every few hundred lines): its position is
    the byte offset of the first line not processed, past multibyte names,
    CRLFs and blank lines, and the resumed poll processes every line
    exactly once."""
    lines = [line for k in range(25) for line in session(EPOCH + k * 3_600_000)]
    log = Written(lines)
    engine, monitor = tail(tmp_path / "Encounter.log", b"")
    write(monitor.log_file, log.data)
    answers = iter([True])
    monitor._process_new_lines(cancel_check=lambda: next(answers, False))
    stopped = monitor.last_position
    assert 0 < stopped < len(log.data), "the poll was not cancelled"
    assert stopped in log.starts
    # A character count would have stopped short of it
    done = log.data[:stopped]
    assert any(byte >= 0x80 for byte in done) and CRLF in done and b"\r\n\r\n" in done
    assert engine.seen == [(at, line) for at, line in log.engine_lines() if at < stopped]
    monitor._process_new_lines()
    assert engine.seen == log.engine_lines()
    assert monitor.last_position == len(log.data)
    assert len(engine.fights) == 50


class Raising(Engine):
    """The engine, raising on one line it cannot take (noted as handed)."""

    def __init__(self, bad):
        super().__init__()
        self.bad = bad

    def process_log_entry(self, entry):
        if entry.original_line == self.bad:
            self.seen.append((self.line_offset, entry.original_line))
            raise ValueError("a line the engine cannot take")
        super().process_log_entry(entry)


def test_a_line_the_engine_raises_on_is_passed_once(tmp_path):
    """A poll whose engine raises on the line after END_COMBAT: the error
    reaches the caller (the engine worker counts failed polls), the fight
    is listed once, the next poll reads on after that line rather than the
    batch again, and the split stays the session's bytes. Each line is
    handed to the engine once, the one that raised included."""
    bad = regen(40100, 3)
    head = [*base(), "20000,BEGIN_COMBAT", *builds(20001, 1, 2, 3),
            player_hits(21000, 1, mob(70, 950000))]
    batch = [player_hits(30000, 2, mob(70, 900000)), "40000,END_COMBAT", bad, regen(40200)]
    later = fight(60000, 70000, player_hits(61000, 2, trash(950000)))
    log = Written(head + batch + later)
    splits = tmp_path / "splits"
    path = write(tmp_path / "Encounter.log", b"")
    engine = Raising(bad)
    monitor = LogFileMonitor(engine, path, tail_and_split=True, split_dir=splits)

    def written(lines):
        with open(path, "ab") as f:
            f.write(Written(lines).data)

    def listed():
        return [event for event in engine.listener.events if event[0] == "fight_completed"]

    written(head)
    monitor._process_new_lines()
    written(batch)
    with pytest.raises(ValueError, match="cannot take"):
        monitor._process_new_lines()
    assert len(engine.fights) == len(listed()) == 1
    assert monitor.last_position == log.at(regen(40200))
    monitor._process_new_lines()
    assert len(engine.fights) == len(listed()) == 1
    assert monitor.last_position == len(Written(head + batch).data)
    written(later)
    monitor._process_new_lines()
    assert len(engine.fights) == len(listed()) == 2
    assert [(f.locator.start_ms, f.locator.end_ms) for f in engine.fights] == [
        (20000, 40000), (60000, 70000)]
    assert engine.seen == log.engine_lines()
    monitor.log_splitter.cleanup()
    (split,) = splits.glob(f"{split_retention.session_stamp(EPOCH)}*.log")
    assert split.read_bytes() == log.data


RESUMED_FIRST =["10000,BEGIN_COMBAT", *builds(10001, 1, 2, 3),
                 player_hits(11000, 2, mob(70, 900000)),
                 player_hits(29000, 2, mob(70, 600000)),
                 "30031,END_COMBAT"]
# Combat begins again 36 ms later, the boss alive and hit between the lines
RESUMED_SECOND = [player_hits(30050, 2, mob(70, 550000)),
                  "30067,BEGIN_COMBAT", *builds(30067, 1, 2, 3),
                  player_hits(40000, 1, mob(70, 450000)),
                  player_hits(50000, 2, mob(70, 0)),
                  "50100,END_COMBAT"]


def test_a_fight_cut_in_two_keeps_its_first_begin_and_takes_its_last_end(tmp_path):
    live = LiveLog(tmp_path / "Encounter.log").write(*base(), *RESUMED_FIRST)
    (entry,) = live.fights
    first = entry.locator
    assert tuple(first[:9]) == placed(live.log, 10000, 30031, None)
    live.write(*RESUMED_SECOND)
    assert live.fights == [entry] and live.fights[0] is entry
    second = entry.locator
    assert second is not first and second != first
    log = live.log
    assert (second.start_ms, second.begin_offset) == (first.start_ms, first.begin_offset)
    assert tuple(second[:9]) == placed(log, 10000, 50100, None)
    assert_on_its_lines(log.data, second)


def test_a_fight_cut_twice_keeps_its_first_begin(tmp_path):
    live = LiveLog(tmp_path / "Encounter.log").write(
        *base(), *RESUMED_FIRST,
        player_hits(30050, 2, mob(70, 550000)), "30067,BEGIN_COMBAT",
        player_hits(40000, 1, mob(70, 500000)), "45000,END_COMBAT",
        player_hits(45040, 1, mob(70, 450000)), "45080,BEGIN_COMBAT",
        player_hits(50000, 2, mob(70, 0)), "50100,END_COMBAT")
    (entry,) = live.fights
    assert tuple(entry.locator[:9]) == placed(live.log, 10000, 50100, None)
    assert_on_its_lines(live.log.data, entry.locator)


TRASH_FIGHT = fight(10000, 20000, player_hits(11000, 2, trash(950000)),
                    player_hits(15000, 3, trash(900000)))


def test_the_fights_own_start_survives_what_comes_after_it(tmp_path):
    """A combat event after END_COMBAT moves the encounter's start (in
    1,130 of 1,152 real encounters), here a late death within the grace;
    the group then fights on and stops (#162), and the next fight begins:
    the locator keeps the BEGIN_COMBAT line's time, and is never rebuilt."""
    live = LiveLog(tmp_path / "Encounter.log").write(*base(), *TRASH_FIGHT)
    (entry,) = live.fights
    located = entry.locator
    assert (located.start_ms, located.end_ms) == (10000, 20000)
    live.write(died(20400, mob(72, 40000, 50000), 3))
    assert entry.deaths == 1 and live.engine.updates(entry) >= 1
    assert live.engine.current_encounter.start_time != 10000   # the trap is live
    before = live.engine.updates(entry)
    live.write(player_hits(21000, 2, trash(860000), 40000),
               player_hits(23000, 3, trash(830000), 30000),
               regen(23000 + FIGHT_ON_MS + 1))
    # Built again with the hits fought on (#162): the fight's 100,000 and these
    assert live.engine.updates(entry) > before
    assert sum(damage for _t, damage in entry.damage_series["all"]) == 100000 + 40000 + 30000
    live.write(*fight(40000, 50000, player_hits(41000, 2, mob(70, 900000))))
    first, second = live.fights
    assert first is entry and entry.locator is located
    log = live.log
    assert tuple(located[:9]) == placed(log, 10000, 20000, None)
    assert tuple(second.locator[:9]) == placed(log, 40000, 50000, None)
    for each in live.fights:
        assert_on_its_lines(log.data, each.locator)


def _mastery_later():
    """Unbound Potential fires in the second fight: the first fight's row
    takes it (a mastery backfill)."""
    return fight(40000, 50000, player_hits(41000, 2, mob(70, 900000)),
                 gained(42000, UNBOUND_POTENTIAL, 1))


@pytest.mark.parametrize("rewrite, lines", [
    ("a fight-on rebuild", [player_hits(21000, 2, trash(860000)),
                            player_hits(23000, 3, trash(830000)),
                            regen(23000 + FIGHT_ON_MS + 1)]),
    ("a late death", [died(20000 + LATE_DEATH_GRACE_MS, mob(72, 40000, 50000), 3)]),
    ("a mastery backfill", _mastery_later()),
    ("an END_TRIAL after the fight", ["21000,END_TRIAL,12,600000,T,100000,30000"]),
])
def test_later_writes_to_the_entry_leave_its_locator(tmp_path, rewrite, lines):
    """The locator is replaced only when a fight the game cut in two goes
    on; every other later write to a delivered entry leaves the same
    object."""
    live = LiveLog(tmp_path / "Encounter.log").write(*base(), *TRASH_FIGHT)
    (entry,) = live.fights
    located = entry.locator
    live.write(*lines)
    assert live.engine.updates(entry) >= 1, f"{rewrite} did not rewrite the entry"
    assert live.fights[0] is entry and entry.locator is located
    if rewrite == "a mastery backfill":
        row = next(p for p in entry.players if p.get("unit_id") == "1")
        assert "Unbound Potential" in row["masteries"]
    if rewrite == "an END_TRIAL after the fight":
        assert entry.trial_result["score"] == 100000


def test_a_zones_line_maps_and_handed_out_ids_are_its_own(tmp_path):
    """zone_offset is the fight's own zone's line; a zone whose only map
    change comes inside a fight's lead-in has no map at the lead; neither
    the last zone's maps nor its units whose id was handed out again reach
    a fight of the next zone, though its lead-in reaches back over the zone
    line."""
    lines = [
        *base(),
        map_changed(5000, MAP_EARLY),
        *fight(20000, 40000, player_hits(21000, 1, mob(70, 900000))),
        monster_added(99000, 71, "Reef Guardian", 50001),   # the trash's id handed out again
        zone_changed(100000, 1263, "Rockgrove", "VETERAN"),
        player_added(100500, 1, "Zoë Testé", "@tëster", 1001, class_id=117, local="T"),
        monster_added(101000, 80, "Oaxiltso", BOSS_HEALTH, boss="T"),
        map_changed(103000, MAP_LEAD),
        *fight(105000, 115000, player_hits(106000, 1, mob(80, 900000)), players=(1,)),
    ]
    log = Written(lines)
    engine = review(write(tmp_path / "Encounter.log", log.data))
    first, second = engine.fights
    assert tuple(first.locator[:9]) == placed(log, 20000, 40000, MAP_EARLY)
    rockgrove = log.at(zone_changed(100000, 1263, "Rockgrove", "VETERAN"))
    assert second.locator.zone_offset == rockgrove
    assert second.locator.map_at_lead is None
    assert tuple(second.locator[3:9]) == (rockgrove, log.at("105000,BEGIN_COMBAT"),
                                          log.at("115000,END_COMBAT"), 105000, 115000, None)
    assert {unit.key for unit in second.locator.units} == {"1", "80"}


def test_a_new_session_starts_without_the_last_ones_maps_and_units(tmp_path):
    """A BEGIN_LOG is a new start even before its zone line (here a session
    the engine reads with none, as a cut log can be): no zone line, no map
    and no handed-out unit of the session before."""
    lines = [
        *base(EPOCH),
        map_changed(5000, MAP_EARLY),
        *fight(20000, 40000, player_hits(21000, 1, mob(70, 900000))),
        monster_added(45000, 71, "Reef Guardian", 50001),   # the trash's id handed out again
        begin_log(OTHER_EPOCH),
        *fight(50000, 60000, player_hits(51000, 1, mob(70, 800000))),
    ]
    log = Written(lines)
    engine = review(write(tmp_path / "Encounter.log", log.data))
    located = engine.fights[1].locator
    second_session = log.starts[log.sessions()[1]]
    assert (located.session_epoch_ms, located.session_offset) == (OTHER_EPOCH, second_session)
    assert located.zone_offset is None and located.map_at_lead is None
    assert located.begin_offset == log.at("50000,BEGIN_COMBAT", log.sessions()[1]) - second_session
    assert "Dreadsail Deckhand" not in {unit.name for unit in located.units}


def unit_lines():
    """A fight from 20 s to 40 s (its range 10 s to 41 s) with every kind
    of unit the table tells apart."""
    return [
        begin_log(EPOCH),
        zone_changed(1000),
        player_added(2000, 1, "Zoë Testé", "@tëster", 1001, class_id=117, local="T"),
        player_added(2000, 2, "Björn Ödegård", "@björn", 1002),
        player_added(2000, 3, "テスト太郎", "@テスト", 1003, grouped="F"),
        player_added(2000, 4, "Drache 𝔘🐉", "@drache", 1004),      # leaves in the lead-in
        player_added(2000, 5, "Früh Weg", "@früh", 1005),           # leaves before it
        player_added(2000, 8, "Ëight Back", "@ëight", 1008),        # back on 18 before the fight
        player_added(2000, 9, "", "", 0),                           # anonymous
        player_added(2000, 16, "Offline", "@spät", 1016),           # a loading placeholder
        monster_added(2500, 70, "Tideborn Taleria", BOSS_HEALTH, boss="T"),
        monster_added(2500, 75, "Sea Adder", SEA_ADDER, boss="T"),
        monster_added(2500, 71, "Dreadsail Deckhand", TRASH_HEALTH),
        monster_added(2500, 73, "Reef Lurker", 50000),
        monster_added(2500, 76, "Dock Worker", 88001, reaction="NPC_ALLY"),
        monster_added(2500, 77, "Early Leaver", 50000),
        monster_added(3000, 90, "Blighted Blastbones", 45478, reaction="NPC_ALLY", owner=1),
        monster_added(3000, 91, "Twilight Matriarch", 45479, reaction="NPC_ALLY", owner=1),
        companion_added(3000, 23, owner=1),
        companion_added(3000, 24, owner=9, reaction="FRIENDLY", monster=MIRRI,
                        name="@quietowner's Companion"),
        *ABILITIES,
        removed(5000, 5),
        removed(9000, 77),
        removed(12000, 8),
        player_added(14000, 18, "Ëight Back", "@ëight", 1008),
        removed(15000, 4),
        "20000,BEGIN_COMBAT",
        *builds(20001, 1, 2, 3, 18, 9),
        player_hits(21000, 1, mob(70, 950000)),
        hit(22000, companion_state(23), mob(70, 900000)),
        removed(25000, 2),
        player_added(26000, 12, "Björn Ödegård", "@björn", 1002),   # back mid-fight
        removed(27000, 23),
        companion_added(28000, 31, owner=1),                        # re-summoned
        removed(30000, 71),
        monster_added(32000, 71, "Reef Guardian", 50001),           # its id handed out again
        monster_added(33000, 73, "Coral Crab", 50002),              # again, with no UNIT_REMOVED
        removed(35000, 90),                                         # the pet gone
        unit_changed(36000, 91, "Twilight Matriarch", 0, "HOSTILE"),   # released: owner 0
        player_hits(37000, 12, mob(70, 850000)),
        "40000,END_COMBAT",
    ]


def test_the_unit_table_is_the_engines_identity_of_the_fights_units():
    engine = feed(unit_lines())
    (entry,) = engine.fights
    located = entry.locator
    kinds = sorted((unit.key, unit.kind) for unit in located.units)
    assert kinds == sorted([
        ("1", fight_locator.SELF), ("2", fight_locator.GROUP), ("3", fight_locator.PLAYER),
        ("4", fight_locator.GROUP), ("18", fight_locator.GROUP), ("9", fight_locator.GROUP),
        ("70", fight_locator.BOSS), ("75", fight_locator.ENEMY),
        ("71", fight_locator.ENEMY), ("71", fight_locator.ENEMY),
        ("73", fight_locator.ENEMY), ("73", fight_locator.ENEMY),
        ("76", fight_locator.OTHER),
        ("90", fight_locator.PET), ("91", fight_locator.PET),
        ("c1-106616", fight_locator.COMPANION), ("c9-103089", fight_locator.COMPANION),
    ])
    (me,) = rows(located, "1")
    assert (me.ids, me.owner, me.name, me.character, me.since_ms, me.until_ms) == (
        ("1",), "", "@tëster", "Zoë Testé", 2000, None)
    # Back on a new unit id mid-fight: one row, both ids
    (back,) = rows(located, "2")
    assert set(back.ids) == {"2", "12"} and back.ids[0] == "2" and back.until_ms is None
    # Back on a new unit id before the fight, re-keyed at BEGIN_COMBAT: the
    # lead-in's id is in the row too
    (rekeyed,) = rows(located, "18")
    assert set(rekeyed.ids) == {"8", "18"} and rekeyed.ids[0] == "18"
    # Left during the lead-in, dropped from the fight's list at BEGIN_COMBAT
    (gone,) = rows(located, "4")
    assert (gone.since_ms, gone.until_ms) == (2000, 15000)
    (anon,) = rows(located, "9")
    assert anon.name == "anon"
    # Boss-flagged: a boss, and a Sea Adder that is not one
    assert [unit.monster_id for unit in rows(located, "70")] == [str(BOSS_HEALTH)]
    assert [unit.monster_id for unit in rows(located, "75")] == [SEA_ADDER]
    # A pet keeps its owner after its UNIT_REMOVED and after its owner field drops to 0
    (pet,) = rows(located, "90")
    assert (pet.owner, pet.until_ms) == ("1", 35000)
    (released,) = rows(located, "91")
    assert released.owner == "1"
    # A companion: its row's key, every unit id it had, the name the fight shows
    (isobel,) = rows(located, "c1-106616")
    assert sorted(isobel.ids) == ["23", "31"] and len(isobel.ids) == 2
    assert (isobel.owner, isobel.monster_id) == ("1", ISOBEL)
    assert isobel.name == companions.shown_name("@tëster")
    assert isobel.since_ms == 3000 and isobel.until_ms is None
    (mirri,) = rows(located, "c9-103089")
    assert (mirri.ids, mirri.owner, mirri.name) == (("24",), "9", companions.shown_name(None))
    assert "quietowner" not in json.dumps(located, default=str)
    # A unit id handed to another monster: a row each, windows apart
    old, new = rows(located, "71")
    assert (old.name, old.since_ms, old.until_ms) == ("Dreadsail Deckhand", 2500, 30000)
    assert (new.name, new.since_ms, new.until_ms) == ("Reef Guardian", 32000, None)
    old, new = rows(located, "73")
    assert (old.name, new.name) == ("Reef Lurker", "Coral Crab")
    assert old.until_ms is not None and old.until_ms <= new.since_ms == 33000
    # Absent: a player gone before the range, an Offline placeholder, an
    # enemy removed before the range, the companions' own unit ids, the OBJECT
    keys = {unit.key for unit in located.units}
    assert not keys & {"5", "16", "77", "23", "24", "31", "95"}
    ids = {unit_id for unit in located.units for unit_id in unit.ids}
    assert not ids & {"5", "16", "77", "95"}


def test_the_table_is_frozen_as_the_entry_is_built():
    """Units the log adds after END_COMBAT are the next fight's, and the
    range ends 1 s after it: one added after end + 1 s is not the fight's,
    whenever the table is taken."""
    engine = feed(unit_lines())
    (entry,) = engine.fights
    feed([monster_added(40000 + TAIL_MS, 79, "Tail Arrival", 50003),
          monster_added(40000 + TAIL_MS + 1, 80, "Late Arrival", 50004)], engine)
    assert not {"79", "80"} & {unit.key for unit in entry.locator.units}
    table = fight_locator.unit_table(engine.current_encounter, 20000, 40000)
    keys = {unit.key for unit in table}
    assert "79" in keys and "80" not in keys


def test_fed_without_offsets_the_locator_has_no_offsets_and_all_the_rest(tmp_path):
    """Tests and scripts feed process_log_entry directly: every offset is
    None, and the times, the map at the lead and the units are those of
    the same lines read from a file."""
    lines = session()
    bare = feed(lines)
    read = review(write(tmp_path / "Encounter.log", Written(lines).data))
    assert len(bare.fights) == len(read.fights) == 2
    for plain, located in zip(bare.fights, read.fights, strict=True):
        loc = plain.locator
        assert (loc.session_offset, loc.zone_offset, loc.begin_offset, loc.end_offset) == (
            None, None, None, None)
        assert loc.session_epoch_ms == EPOCH
        assert loc == located.locator._replace(session_offset=None, zone_offset=None,
                                               begin_offset=None, end_offset=None)
        assert loc.units


def test_the_split_is_the_sessions_bytes_under_polls_cut_inside_lines(tmp_path):
    """Splitting on, the live tail polled inside lines, between CR and LF,
    inside multibyte characters and one byte into each BEGIN_LOG: each
    session's split is its bytes in the log, the lines the parser rejects
    included."""
    first, second = session(EPOCH, blanks=False), session(OTHER_EPOCH, blanks=False)
    log = Written(first + second)
    splits = tmp_path / "splits"
    engine, monitor = tail(tmp_path / "Encounter.log", log.data, cut_points(log.data),
                           tail_and_split=True, split_dir=splits)
    monitor.log_splitter.cleanup()
    bounds = [log.starts[i] for i in log.sessions()] + [len(log.data)]
    for k, (epoch, (start, end)) in enumerate(zip((EPOCH, OTHER_EPOCH), pairwise(bounds),
                                                  strict=True)):
        (split,) = splits.glob(f"{split_retention.session_stamp(epoch)}*.log")
        assert split.read_bytes() == log.data[start:end]
        # So the live log's offsets hold in the split, and in the split zipped
        tailed = [f.locator._replace(session_offset=0) for f in engine.fights[2 * k:2 * k + 2]]
        assert [f.locator for f in review(split).fights] == tailed
        packed = zipped(tmp_path / f"{split.name}.zip", split.name, split.read_bytes())
        assert [f.locator for f in review(packed).fights] == tailed


def test_an_lf_logs_split_is_crlf(tmp_path):
    """The splitter writes CRLF whatever the log's line ends, so an LF
    log's offsets are not its split's (real logs are CRLF)."""
    lines = session(blanks=False)
    lf = Written(lines, LF)
    splits = tmp_path / "splits"
    _engine, monitor = tail(tmp_path / "Encounter.log", lf.data, cut_points(lf.data),
                            tail_and_split=True, split_dir=splits)
    monitor.log_splitter.cleanup()
    (split,) = splits.glob(f"{split_retention.session_stamp(EPOCH)}*.log")
    assert split.read_bytes() == Written(lines, CRLF).data


def test_a_held_combat_listed_by_a_late_death_spans_its_own_lines(tmp_path):
    """Combat with no enemy is held at END_COMBAT (#182) and listed only by
    a death in the grace; a combat event in between moved the encounter's
    start, yet the fight is its own BEGIN_COMBAT to its END_COMBAT."""
    live = LiveLog(tmp_path / "Encounter.log").write(
        begin_log(EPOCH),
        zone_changed(1000, 1227, "Vateshran Hollows", "VETERAN"),
        player_added(2000, 1, "Zoë Testé", "@tëster", 1001, class_id=117, local="T"),
        player_added(2000, 2, "Björn Ödegård", "@björn", 1002),
        monster_added(2500, 81, "Storm", 56034, reaction="NPC_NEUTRAL"),
        *ABILITIES,
        "10000,BEGIN_COMBAT", *builds(10001, 1, 2),
        hit(15000, TRAP, state(1, 0), 20000),
        "15010,END_COMBAT")
    assert live.fights == []
    live.write(hit(15050, TRAP, state(2, 16000), 4000))
    assert live.engine.current_encounter.start_time != 10000   # moved by that event
    assert live.fights == []
    live.write(died(15095, TRAP, 1))
    (entry,) = live.fights
    assert entry.deaths == 1
    assert tuple(entry.locator[:9]) == placed(live.log, 10000, 15010, None)
    assert_on_its_lines(live.log.data, entry.locator)


def test_combat_with_no_begin_combat_line_has_no_begin_offset(tmp_path):
    """Combat the log opens no BEGIN_COMBAT for: no begin offset, its
    END_COMBAT placed as any other."""
    log = Written([*base(), player_hits(11000, 2, mob(70, 900000)),
                   player_hits(15000, 3, mob(70, 800000)), "20000,END_COMBAT"])
    (entry,) = review(write(tmp_path / "Encounter.log", log.data)).fights
    located = entry.locator
    assert located.begin_offset is None
    assert (located.session_offset, located.end_ms) == (0, 20000)
    assert line_at(log.data, located.end_offset) == b"20000,END_COMBAT"
    assert located.start_ms == 20000 - round(entry.duration_s * 1000)


def test_an_end_combat_in_a_later_session_is_not_placed_in_the_fights(tmp_path):
    """Logging restarted mid-fight: the END_COMBAT is in another session,
    so no offset from the fight's BEGIN_LOG names it."""
    log = Written([*base(EPOCH), "10000,BEGIN_COMBAT", *builds(10001, 1, 2, 3),
                   player_hits(11000, 2, mob(70, 900000)),
                   begin_log(OTHER_EPOCH),
                   player_hits(12000, 2, mob(70, 800000)), "20000,END_COMBAT"])
    (entry,) = review(write(tmp_path / "Encounter.log", log.data)).fights
    located = entry.locator
    assert (located.session_offset, located.session_epoch_ms) == (0, EPOCH)
    assert line_at(log.data, located.begin_offset) == b"10000,BEGIN_COMBAT"
    assert located.end_offset is None


def test_a_log_with_no_begin_log_has_no_offsets(tmp_path):
    """A log that opens mid-session (a cut file): no BEGIN_LOG, so nothing
    to count from."""
    lines = [line for line in session() if ",BEGIN_LOG," not in line]
    engine = review(write(tmp_path / "headless.log", Written(lines).data))
    assert len(engine.fights) == 2
    for entry in engine.fights:
        located = entry.locator
        assert (located.session_offset, located.zone_offset, located.begin_offset,
                located.end_offset) == (None, None, None, None)
        assert (located.start_ms, located.end_ms) in (FIRST, SECOND)


def _replay_fails(self, start, end):
    raise RuntimeError("the replay failed")


def test_the_roster_sweep_says_where_the_session_begins(tmp_path, monkeypatch):
    """The attach's replay failed, so the roster sweep reads the session's
    head (as it does for a BEGIN_LOG beyond the lookback): its BEGIN_LOG
    and zone line keep their offsets, and the fights the tail then reads
    are placed as a review places them."""
    first, second = session(EPOCH), session(OTHER_EPOCH)
    log = Written(first + second)
    cut = log.at(map_changed(5000, MAP_EARLY), len(first))   # the second session's head
    path = write(tmp_path / "Encounter.log", log.data[:cut])
    monkeypatch.setattr(LogFileMonitor, "_process_range", _replay_fails)
    engine, monitor = attach(path)
    assert engine.fights == []
    assert engine.session_offset == len(Written(first).data)
    with open(path, "ab") as f:
        f.write(log.data[cut:])
    monitor._process_new_lines()
    assert [tuple(f.locator[:9]) for f in engine.fights] == [
        placed(log, *FIRST, MAP_EARLY, 1), placed(log, *SECOND, MAP_FIGHT, 1)]
    for entry in engine.fights:
        assert_on_its_lines(log.data, entry.locator)


def test_the_roster_sweep_keeps_the_map_in_force(tmp_path, monkeypatch):
    """The roster sweep reads the session's MAP_CHANGED lines too, so a
    fight the tail reads after a sweep has the map named before it."""
    log = Written(session())
    cut = log.at("20000,BEGIN_COMBAT")   # after both maps, before the first fight
    path = write(tmp_path / "Encounter.log", log.data[:cut])
    monkeypatch.setattr(LogFileMonitor, "_process_range", _replay_fails)
    engine, monitor = attach(path)
    with open(path, "ab") as f:
        f.write(log.data[cut:])
    monitor._process_new_lines()
    assert [f.locator.map_at_lead for f in engine.fights] == [MAP_EARLY, MAP_FIGHT]


def test_a_new_file_attached_to_the_same_engine_starts_without_a_session(tmp_path):
    """The log vanished and a new one appeared: the engine worker attaches
    the same engine to it. One that opens with no BEGIN_LOG has no session
    to count from, not the last file's."""
    tiny = [begin_log(EPOCH - 3_600_000), zone_changed(3, 57, "Deshaan", "NONE"), "120,END_LOG"]
    old = Written(tiny + session(EPOCH))
    engine = Engine()
    old_path = write(tmp_path / "Encounter.log", old.data)
    LogFileMonitor(engine, old_path)
    assert engine.session_offset == len(Written(tiny).data) > 0
    assert engine.session_epoch_ms == EPOCH
    lines = [line for line in session(OTHER_EPOCH) if ",BEGIN_LOG," not in line]
    new = Written(lines)
    cut = new.at(map_changed(5000, MAP_EARLY))
    path = write(tmp_path / "Encounter-new.log", new.data[:cut])
    monitor = LogFileMonitor(engine, path)
    with open(path, "ab") as f:
        f.write(new.data[cut:])
    monitor._process_new_lines()
    fights = engine.fights[2:]
    assert len(fights) == 2
    # The old file still holds the last file's session, at the same times
    places = [fight_reread.Place(path, "live"), fight_reread.Place(old_path, "live")]
    for entry in fights:
        located = entry.locator
        assert (located.session_offset, located.zone_offset, located.begin_offset,
                located.end_offset) == (None, None, None, None)
        # Nor the last file's session: the fight is not read from it (the
        # view draws no link for it), and a read says why
        assert located.session_epoch_ms is None
        with pytest.raises(fight_reread.NotOnDisk) as caught:
            fight_reread.read_fight(located, places)
        assert [why for _place, why in caught.value.reasons] == [fight_reread.NOT_KNOWN] * 2


def test_a_log_truncated_and_written_again_counts_from_its_new_start(tmp_path):
    """The engine worker's poll starts over at 0 when the log shrank (a
    new log written in place of the old): the new session's offsets are
    the new file's."""
    old = Written(session(EPOCH) + session(OTHER_EPOCH))
    engine, monitor = tail(tmp_path / "Encounter.log", old.data)
    assert len(engine.fights) == 4
    new = Written(session(OTHER_EPOCH + 3_600_000))
    write(monitor.log_file, new.data)
    assert monitor.log_file.stat().st_size < monitor.last_position
    monitor.last_position = 0   # as EngineWorker._poll does
    monitor._process_new_lines()
    fresh = engine.fights[4:]
    assert [tuple(f.locator[:9]) for f in fresh] == [
        placed(new, *FIRST, MAP_EARLY), placed(new, *SECOND, MAP_FIGHT)]
    for entry in fresh:
        assert_on_its_lines(new.data, entry.locator)


def test_the_read_all_path_reads_text_so_gives_no_offsets(tmp_path):
    """read_all_then_tail (which no app path runs) reads text: no offsets
    rather than wrong ones."""
    log = Written(session())
    engine, _monitor = attach(write(tmp_path / "Encounter.log", log.data),
                              read_all_then_tail=True)
    assert len(engine.fights) == 2
    for entry, times in zip(engine.fights, (FIRST, SECOND), strict=True):
        located = entry.locator
        assert (located.session_offset, located.begin_offset, located.end_offset) == (
            None, None, None)
        assert (located.start_ms, located.end_ms) == times


def test_a_zip_member_reads_as_the_logs_own_bytes(tmp_path):
    data = Written(session()).data
    plain = write(tmp_path / "s.log", data)
    one = zipped(tmp_path / "s.log.zip", "s.log", data)
    for path in (plain, one):
        with open_log_bytes(path) as (f, total, shown):
            lines = list(f)
        assert lines == data.splitlines(keepends=True) and total == len(data)
        assert shown == str(path)
    two = tmp_path / "two.zip"
    with zipfile.ZipFile(two, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.log", b"x\r\n")
        zf.writestr("b.log", data)
    with open_log_bytes(two, "b.log") as (f, total, shown):
        assert f.read() == data and total == len(data) and shown.endswith("b.log")


def test_the_maps_kept_are_the_zones_last(tmp_path):
    """More map changes than are kept: the map at the lead is still the
    last written before it."""
    maps = [MapFrame(str(3000 + k), f"Map {k}", f"art/map_{k}") for k in range(MAPS_KEPT + 4)]
    lines = [*base(), *(map_changed(3000 + k * 100, frame) for k, frame in enumerate(maps)),
             *fight(20000, 30000, player_hits(21000, 1, mob(70, 900000)))]
    (entry,) = review(write(tmp_path / "Encounter.log", Written(lines).data)).fights
    assert entry.locator.map_at_lead == maps[-1]


@pytest.mark.parametrize("where", ["one byte into BEGIN_LOG", "inside a hit, no BEGIN_LOG"])
def test_an_attach_that_sweeps_still_reads_the_line_being_written_whole(tmp_path, where):
    """An attach that finds no whole BEGIN_LOG to replay from (the game has
    written only part of the session's first line, or the log opens
    mid-session) sweeps for a roster, and the tail goes on from the line
    the game is writing, which it reads once, whole."""
    lines = session()
    if where == "one byte into BEGIN_LOG":
        log = Written(lines)
        cut, start = 1, 0
    else:
        log = Written([line for line in lines if ",BEGIN_LOG," not in line])
        line = player_hits(26000, 2, mob(70, 900000))
        start = log.at(line)
        cut = start + len(line) // 2
    path = write(tmp_path / "Encounter.log", log.data[:cut])
    engine, monitor = attach(path)
    with open(path, "ab") as f:
        f.write(log.data[cut:])
    monitor._process_new_lines()
    assert (start, log.lines[log.starts.index(start)]) in engine.seen
    assert monitor.last_position == len(log.data)


def test_the_roster_sweep_leaves_a_line_across_the_attach_point_to_the_tail(tmp_path,
                                                                            monkeypatch):
    """A line the game finished between the attach taking the log's size and
    the sweep reading it begins before the attach point. The sweep takes
    only roster lines, so it leaves that line to the tail, which reads it
    once, whole, at its first byte."""
    log = Written([line for line in session() if ",BEGIN_LOG," not in line])
    line = player_hits(26000, 2, mob(70, 900000))
    start = log.at(line)
    path = write(tmp_path / "Encounter.log", log.data)
    monkeypatch.setattr(LogFileMonitor, "_load_latest_session", lambda self: None)
    engine, monitor = attach(path)
    monitor.last_position = start + len(line) // 2   # the size as the attach took it
    monitor._backfill_session_preamble()
    assert monitor.last_position == start
    monitor._process_new_lines()
    assert [seen for seen in engine.seen if seen[0] == start] == [(start, line)]
    assert monitor.last_position == len(log.data)



def test_ids_handed_out_again_in_a_zone_with_no_fight_are_not_all_kept(tmp_path):
    """Hours in a city hand unit ids out again and again: the engine keeps
    only the replaced units a fight could still need, so they do not pile
    up (the review of PR #224)."""
    from esolog_tail import REPLACED_UNITS_KEPT
    lines = [begin_log(EPOCH), zone_changed(3, 1011, "A City", "NONE")]
    lines += [monster_added(1000 + k * 100, 500, f"Citizen {k}", "5555", reaction="NPC_ALLY")
              for k in range(3 * REPLACED_UNITS_KEPT)]
    engine = review(write(tmp_path / "Encounter.log", Written(lines).data))
    kept = engine._replaced_units
    assert 0 < len(kept) <= REPLACED_UNITS_KEPT
    newest = 1000 + (3 * REPLACED_UNITS_KEPT - 1) * 100
    assert max(when for _unit, when in kept) == newest
