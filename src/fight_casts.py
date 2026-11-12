"""
Every group player's casts in a fight, packed for the fight's entry, for the
Events tab's actions (issue #214, action_rows): when each cast began, the
ability, the unit it was aimed at and how long it lasted.

Design: one player's casts on the fight entry (issue #214). The casts are
casts.CastRecorder's, the ones the Build tab counts: one per castTrackId,
a synergy taken again counted, a proc left out unless it is of a skill on
the player's bars (#226), taken by the same call (cast_records) the
counts are, for each player row of the fight, so a player's casts here are
their row's casts['total'] (the replay below checks it). Companions' casts
are left out. Each cast keeps:

- its time, from the fight's start (the casts begun before the pull are
  not the fight's, as in the counts);
- its ability id; the names and icons are a table of the fight's abilities;
- the unit it was aimed at, named as the cast is noted, as fight_events
  names its units (an id is handed out again in a later zone): the target
  unit of the BEGIN_CAST line, unless the line names none ('0') or the
  caster ('*', or the caster's own unit or record);
- its length: the time from its BEGIN_CAST to its END_CAST, when the log
  wrote one, never the BEGIN_CAST's own duration field; and whether that
  END_CAST says INTERRUPTED. A cancelled cast's END_CAST (PLAYER_CANCELLED)
  never reaches the engine, as the parser rejects it, so that cast has no
  length.

The form: a fight's casts are packed when its entry is built, like the
events (fight_events), into one bytes object of fixed-size records for
each player, a table of the targets they name and a table of the
abilities, immutable as an entry must be once it crosses to the GUI's
thread. A record is 17 bytes (time, ability id, target, length, flags).
Kept apart from the events rather than in them: an event's record is 38
bytes, and a cast needs none of its strings but the target. The casts
live as the events do: built with the entry, gone from the recorder at the
fight's start but when the build is the one the group fighting on asks
for (again), and taken by that rebuild (waiting_hits.FOUGHT_ON_SLOTS)
with the deaths and the events, an END_CAST read after END_COMBAT then
giving the cast its length.
"""

import struct
from collections import namedtuple
from collections.abc import Callable, Iterable

from casts import CAST_ABILITY, CAST_END, CAST_FLAGS, CAST_TARGET, CAST_TIME
from casts import INTERRUPTED as _RECORDER_INTERRUPTED

# Flags on a record
ENDED = 1          # the log wrote the cast's END_CAST
INTERRUPTED = 2    # ... and it said INTERRUPTED

# time (ms from the fight's start), ability id, target (an index into the
# fight's targets, 0 for none), length (ms from BEGIN_CAST to END_CAST, 0
# without one), flags. Targets are 32-bit, as fight_events' strings: a long
# stretch of open-world combat can name many units
_RECORD = struct.Struct("<iIIiB")
_ID = struct.Struct("<I")

Cast = namedtuple("Cast", "t ability_id target target_key length flags")


class FightCasts:
    """One fight's casts, packed (see the module): immutable, read with
    of(key) in the order cast. Times are in ms from the fight's start."""

    __slots__ = ("_abilities", "_blobs", "_icons", "_keys", "_names", "_target_keys",
                 "_targets")

    def __init__(self, keys: tuple, blobs: tuple, targets: tuple, target_keys: tuple,
                 ability_ids: bytes, names: tuple, icons: tuple):
        self._keys = keys            # each player's record id
        self._blobs = blobs          # their casts, packed, in the same order
        self._targets = targets      # each target's name, '' at 0 for none
        self._target_keys = target_keys
        self._abilities = ability_ids  # every ability id named, packed
        self._names = names          # ... and its name and icon stem
        self._icons = icons

    def __len__(self) -> int:
        return sum(len(blob) for blob in self._blobs) // _RECORD.size

    def __eq__(self, other) -> bool:
        return (isinstance(other, FightCasts) and self._keys == other._keys
                and self._blobs == other._blobs and self._targets == other._targets
                and self._target_keys == other._target_keys
                and self._abilities == other._abilities and self._names == other._names
                and self._icons == other._icons)

    def __hash__(self):
        return hash(self._blobs)

    def __repr__(self) -> str:
        return f"FightCasts({len(self._keys)} players, {len(self)} casts)"

    def keys(self) -> tuple:
        """The record ids of the players whose casts are kept."""
        return self._keys

    def count(self, key: str) -> int:
        """How many casts the player *key* began in the fight."""
        try:
            return len(self._blobs[self._keys.index(str(key))]) // _RECORD.size
        except ValueError:
            return 0

    def of(self, key: str) -> list[Cast]:
        """The player *key*'s casts in the order begun; [] for a player
        with none kept."""
        try:
            blob = self._blobs[self._keys.index(str(key))]
        except ValueError:
            return []
        targets, target_keys = self._targets, self._target_keys
        return [Cast(t, str(ability), targets[target], target_keys[target], length, flags)
                for t, ability, target, length, flags in _RECORD.iter_unpack(blob)]

    def abilities(self) -> dict[str, tuple[str, str]]:
        """Ability id -> (name, icon stem) for the abilities the casts name."""
        ids = (str(ability) for (ability,) in _ID.iter_unpack(self._abilities))
        return {ability: (name, icon) for ability, name, icon in zip(ids, self._names, self._icons)}

    @property
    def nbytes(self) -> int:
        """The records' bytes (the tables of targets and abilities aside)."""
        return sum(len(blob) for blob in self._blobs)


def pack(players: Iterable[tuple[str, list]], start: int,
         ability: Callable[[str], tuple[str, str]] = lambda a: (a, "")) -> FightCasts:
    """The casts of *players*, (record id, the recorder's casts of the
    fight: casts.CastRecorder.cast_records), packed with times from
    *start* (raw ms). *ability* names an ability id: (name, icon stem)."""
    keys, blobs = [], []
    targets: dict[tuple, int] = {("", ""): 0}
    abilities: dict[str, int] = {}
    for key, casts in players:
        packed = bytearray()
        for cast in casts:
            ability_id = cast[CAST_ABILITY]
            if ability_id not in abilities:
                abilities[ability_id] = len(abilities)
            target = cast[CAST_TARGET]
            index = 0 if target is None else targets.setdefault(target, len(targets))
            end = cast[CAST_END]
            flags = 0
            if end is not None:
                flags = ENDED | (INTERRUPTED if cast[CAST_FLAGS] & _RECORDER_INTERRUPTED else 0)
            packed += _RECORD.pack(cast[CAST_TIME] - start,
                                   int(ability_id) if ability_id.isdigit() else 0, index,
                                   max(0, end - cast[CAST_TIME]) if end is not None else 0, flags)
        keys.append(str(key))
        blobs.append(bytes(packed))
    ids = bytearray()
    names, icons = [], []
    for ability_id in abilities:
        ids += _ID.pack(int(ability_id) if ability_id.isdigit() else 0)
        name, icon = ability(ability_id)
        names.append(name)
        icons.append(icon)
    order = sorted(targets, key=targets.get)
    return FightCasts(tuple(keys), tuple(blobs), tuple(name for name, _key in order),
                      tuple(key for _name, key in order), bytes(ids), tuple(names), tuple(icons))


def casts_of(entry, key: str) -> list[Cast]:
    """The casts of the player *key* in *entry*, [] for an entry built
    before the casts were kept (FightHistoryEntry.casts None)."""
    casts = getattr(entry, "casts", None)
    return casts.of(key) if casts is not None else []
