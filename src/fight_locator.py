"""
Where a fight's lines are in its log, and who its units are (issue #214):
the locator the engine keeps on each fight's entry, by which a view
re-reads that one fight from disk (fight_reread) instead of the engine
holding every unit's place for the whole session.

Design: Byte offsets from the session's BEGIN_LOG line. The locator holds
the offsets of the fight's BEGIN_COMBAT and END_COMBAT lines and of its
zone's ZONE_CHANGED line, each counted in bytes from the first byte of the
session's BEGIN_LOG line, with that line's own offset in the file the
engine read and its Unix milliseconds. Counted from the session, an offset
is the same number in the live log, in the session's split and in a zipped
split's member: a split written since 0.19.0 is its session's bytes (6 of 6
sessions of the live log byte-identical to their splits, 116 MB down to
11 MB), and a zip's member is a byte copy of the split. Every reader that
feeds the engine therefore reads bytes and says where each line starts
(``ESOLogAnalyzer.line_offset``): the live tail, the attach and Settings-save
replay, the review of a plain or zipped log, and the roster sweep.
Characters are not bytes: over the 411 split logs (35 GiB, 213.5 million
lines, every one ending CRLF) text mode falls 213,527,919 characters short
of the bytes, one per CRLF plus 1,257 for the multibyte letters of player
names. Reading bytes costs nothing: whole engine passes over a Rockgrove
and a Kyne's Aegis split ran 0.1% and 0.4% faster than in text, with the
same fights, and the counting itself is 0.03 µs a line. The live tail
holds back a last line the game has not finished writing, so every line
reaches the engine once, whole, with its offset; so do the attach replay
and the roster sweep at the point where they hand over to the tail. Read
in text, a poll that landed inside a line handed the parser two broken
lines, and in a test a fight was lost that way. In all 8,932 fights of the
391 split logs (35.8 GB), 448 of them fights the game cut in two or more,
the BEGIN_LOG, ZONE_CHANGED, BEGIN_COMBAT and END_COMBAT lines were at
their recorded offsets, and every other field of every entry was as
before. Ten splits zipped as retention zips them gave the same locators
(186 fights), and so did two logs of three sessions each, attached to and
tailed in about 1,180 polls each, nine in ten of them ending inside a line;
the splits that tail wrote were byte-identical to their sessions.

A split written before 0.19.0 lacks the lines the parser rejects (a
cancelled cast, an OBJECT unit): a median 7.7 KB before a fight's
BEGIN_COMBAT, so an offset taken from the live log lands late in it. So
the reader checks the lines before trusting the offsets: the line at the
session's base is a BEGIN_LOG with the session's Unix milliseconds, and the
line at the BEGIN_COMBAT offset is ``<start ms>,BEGIN_COMBAT``; when either
fails it finds the fight by its times within the session.

The fight's times are its BEGIN_COMBAT and END_COMBAT lines' (start_ms,
end_ms), taken as the entry is built, where every path that builds one has
restored the fight's own start. Read at any later moment the encounter's
start is not the fight's: a combat event after END_COMBAT sets the
encounter in combat again and moves it, which at the next BEGIN_COMBAT had
happened in 1,130 of 1,152 encounters, by a median of 16 s and up to 441 s.

The range a view reads is not stored: from LEAD_MS before BEGIN_COMBAT
(the moments the opener and the group's waiting hits read, fight_opener,
waiting_hits) to TAIL_MS after END_COMBAT (the late-death grace). The
reader finds its first line by time, reading back from the BEGIN_COMBAT
line, never past the zone's ZONE_CHANGED line (unit ids start over there)
or the session's BEGIN_LOG; over the 411 splits those 10 s held a median
128 KB and at most 2.0 MB. It reads on past END_COMBAT to the first line
after the tail, and stops at the next BEGIN_COMBAT, ZONE_CHANGED, BEGIN_LOG
or END_LOG: over the 391 splits the next fight's BEGIN_COMBAT came within
the tail in 801 of 8,932 fights, and 3,301 lead-ins reached back over the
fight before. The group fighting on after END_COMBAT (#162, waiting_hits)
is not in the range: that rebuild takes only the damage figures and keeps
the locator, so the seconds the DPS graph shows past the fight's end are
outside the view, as the fight's clock, deaths and recaps are.

The map. The log's coordinates are fractions of the map last named by a
MAP_CHANGED line, and a lead-in held one in 980 of 8,932 fights (11%), so
the locator carries the map in force at the lead-in's first line
(map_at_lead), and the reader switches maps at each MAP_CHANGED line in the
file's order. MAP_CHANGED lines are kept per zone (MAPS_KEPT).

The unit table is the engine's identity of the fight's units, frozen as the
entry is built, so a re-read never works out who a unit is. A player's row
holds every unit id they had in the fight: their record's, the ids they came
back on (presence.py, rule 3) and the ids they were known by as BEGIN_COMBAT
redid the roster. A companion's row holds every unit id the companion had,
under its row's key and the name the fight shows (companions.shown_name,
never the log's). A pet keeps its owner after its UNIT_REMOVED or its owner
field dropping to 0, which the engine's own map of pets forgets: a table
taken from that map at the fight's end gave the wrong owner on 1.52% of
the unit states in the fights' ranges, in 206 of 545 fights; keeping each
pet's last owner left 0.011%. Monsters, NPCs and pets are listed when they
were in the zone during the range; each row's window (since_ms, until_ms,
its UNIT_ADDED and UNIT_REMOVED, a player's arrival and departure) tells
apart a unit id handed to another unit, the latest arrival winning. Units the
log never announced in the zone (anchors, hazards) and objects, whose
UNIT_ADDED the parser rejects, are not in it: over one split of each of 21
zones, 99.04% of the 7.7 million unit states in the fights' ranges were of
a unit in the table, every state of a unit in it was, and the reader reads
the rest as unknown units. As tuples the locator is a median 29 KB for a
12-player boss fight (p90 74 KB), 1.4 to 1.6 MB for three hours of trials.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple

# The range a view reads: from this long before BEGIN_COMBAT (the opener's
# and the waiting hits' window) to this long after END_COMBAT (the
# late-death grace)
LEAD_MS = 10_000
TAIL_MS = 1_000
# MAP_CHANGED lines kept for the zone, the last ones written
MAPS_KEPT = 16

# A unit's kind in the table: the logging player, a member of their group,
# any other player, a companion, a player's pet, a boss (the game's flag
# less boss_units' exceptions), any other hostile unit, anything else
SELF = "self"
GROUP = "group"
PLAYER = "player"
COMPANION = "companion"
PET = "pet"
BOSS = "boss"
ENEMY = "enemy"
OTHER = "other"


class MapFrame(NamedTuple):
    """A map the log's coordinates are fractions of, from its MAP_CHANGED
    line: the map's id, name and texture."""
    map_id: str
    name: str
    texture: str


class FightUnit(NamedTuple):
    """One unit of a fight as the engine knew it.

    *ids*: every unit id it had in the fight, its record's first; *kind*:
    SELF, GROUP, PLAYER, COMPANION, PET, BOSS, ENEMY or OTHER; *key*: the
    engine's key for it, a player's record id or a companion's row key (the
    'unit_id' of its row in the entry's players, when it has one), else its
    unit id; *owner*: the owner's record id for a pet or companion, else '';
    *name*: the name the fight shows (a player's display name, as in the
    entry's player_names); *character*: a player's character name;
    *monster_id*: the game's id of a monster or NPC; *since_ms* and
    *until_ms*: when it came into the zone and left it, None when not seen.
    """
    ids: tuple
    kind: str
    key: str
    owner: str
    name: str
    character: str
    monster_id: str
    since_ms: int | None
    until_ms: int | None


class FightLocator(NamedTuple):
    """Where a fight's lines are and who its units are (see the module).

    Offsets are bytes from the first byte of the session's BEGIN_LOG line,
    None where the reader that fed the engine gave none (a test, a script)
    or no BEGIN_LOG was seen; *session_offset* is that line's own offset in
    the file the engine read, a hint for a log of several sessions;
    *begin_offset* is None for combat that had no BEGIN_COMBAT line (a
    session that opens mid-fight). *start_ms* and *end_ms* are the
    BEGIN_COMBAT and END_COMBAT lines' times, ms since BEGIN_LOG.
    """
    session_stamp: str
    session_epoch_ms: int | None
    session_offset: int | None
    zone_offset: int | None
    begin_offset: int | None
    end_offset: int | None
    start_ms: int
    end_ms: int
    map_at_lead: MapFrame | None
    units: tuple


class FightStart(NamedTuple):
    """What the engine knows of a fight's place as its BEGIN_COMBAT line
    passes: the line's offset in the file, the session's and the zone's
    (offset in the file, Unix ms, stamp), the map in force at the lead-in,
    and the zone's players with the unit ids they were known by before the
    roster was redone (roster_ids)."""
    offset: int | None
    session_offset: int | None
    session_epoch_ms: int | None
    session_stamp: str
    zone_offset: int | None
    map_at_lead: MapFrame | None
    roster: tuple


def map_before(maps: Iterable[tuple], before_ms: int) -> MapFrame | None:
    """The map in force before *before_ms*: the last of the zone's
    (line time, MapFrame) changes, in file order, written before it; None
    when none was."""
    found = None
    for at, frame in maps:
        if at >= before_ms:
            break
        found = frame
    return found


def roster_ids(players: Iterable) -> tuple:
    """Each player record with the unit ids it is known by, as a fight's
    BEGIN_COMBAT passes and before the roster is redone (presence.py): a
    player who left is dropped there, and one who came back on a new unit
    id is re-keyed by it, so their lead-in states would otherwise name
    nobody."""
    return tuple((player, frozenset({player.unit_id, player.latest_unit_id}
                                    | player.alias_ids))
                 for player in players)


def locate(start: FightStart, end_offset: int | None, start_ms: int, end_ms: int,
           units: tuple) -> FightLocator:
    """The fight's locator from its FightStart, its END_COMBAT line's offset
    in the file (None when unknown) and its times and units."""
    base = start.session_offset

    def from_session(offset):
        if offset is None or base is None or offset < base:
            return None
        return offset - base

    return FightLocator(start.session_stamp, start.session_epoch_ms, base,
                        from_session(start.zone_offset), from_session(start.offset),
                        from_session(end_offset), start_ms, end_ms, start.map_at_lead, units)


def _present(since: int | None, until: int | None, lead: int, tail: int) -> bool:
    return (since is None or since <= tail) and (until is None or until >= lead)


def _ids_first(ids: set, first: str) -> tuple:
    """*ids* with *first* at their head and the rest in numeric order (unit
    ids are digits)."""
    rest = sorted((unit_id for unit_id in ids if unit_id != first), key=lambda u: (len(u), u))
    return (first, *rest) if first in ids else tuple(rest)


def unit_table(enc, start_ms: int, end_ms: int, roster: tuple = (),
               replaced: Iterable[tuple] = ()) -> tuple:
    """The fight's units as FightUnit rows (see the module): the players of
    *enc* (a CombatEncounter) and of *roster* (roster_ids at its
    BEGIN_COMBAT), its companions, and its monsters, NPCs and pets, with
    *replaced*, the (record, when) of the zone's units whose id was handed
    to a new unit, that were in the zone during the range."""
    lead, tail = start_ms - LEAD_MS, end_ms + TAIL_MS
    units = []

    player_ids: dict = {}
    for player, ids in roster:
        player_ids.setdefault(player, set()).update(ids)
    for player in enc.players.values():
        player_ids.setdefault(player, set()).update(
            {player.unit_id, player.latest_unit_id} | player.alias_ids)
    for player, ids in player_ids.items():
        if not _present(player.joined_at, player.left_at, lead, tail):
            continue
        kind = SELF if player.is_local else GROUP if player.grouped else PLAYER
        units.append(FightUnit(_ids_first(ids, player.unit_id), kind, player.unit_id, "",
                               player.get_display_name(), player.name, "",
                               player.joined_at, player.left_at))

    # Every unit id of each companion, kept together under its row's key
    companion_of = {}
    for record in enc.companions.values():
        for unit_id in record.unit_ids:
            companion_of[unit_id] = record
    companions: dict = {}
    records = [(enemy, enemy.removed_at) for enemy in enc.enemies.values()]
    records += [(enemy, when if enemy.removed_at is None else min(enemy.removed_at, when))
                for enemy, when in replaced]
    for enemy, until in records:
        if not _present(enemy.added_at, until, lead, tail):
            continue
        record = companion_of.get(enemy.unit_id)
        if enemy.is_companion and record is not None and record.monster_id == enemy.monster_id:
            held = companions.get(record.key)
            if held is None:
                companions[record.key] = [record, {enemy.unit_id}, enemy.added_at, until]
            else:
                held[1].add(enemy.unit_id)
                held[2] = _earlier(held[2], enemy.added_at)
                held[3] = None if held[3] is None or until is None else max(held[3], until)
            continue
        owner = enemy.owner_player
        if owner is not None:
            kind, owner_key = PET, owner.unit_id
        else:
            kind, owner_key = (BOSS if enemy.is_boss else ENEMY) if enemy.is_hostile else OTHER, ""
        units.append(FightUnit((enemy.unit_id,), kind, enemy.unit_id, owner_key, enemy.name, "",
                               enemy.monster_id, enemy.added_at, until))
    for key, (record, ids, since, until) in companions.items():
        units.append(FightUnit(_ids_first(ids, ""), COMPANION, key, record.owner_unit_id,
                               record.name, "", record.monster_id, since, until))
    return tuple(units)


def _earlier(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    return min(a, b)
