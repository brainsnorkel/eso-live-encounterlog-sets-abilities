"""
A fight's notable events, kept as the engine reads the log, for the Events
tab (issue #214): the bosses' casts and health, the big hits on the group,
the taunts, the resurrections and the fight's phases. The deaths are the
entry's own (death_recaps); event_rows turns both into the tab's rows.

Design: the notable events of a fight, recorded in the engine's pass
(issue #214). The study of #214 weighed three ways to give a view a fight's
moments: record them as the engine reads the log, read the fight again from
disk when the view opens, or record where the lines are and read them then.
The maintainer chose to record: a re-read depends on the log still being on disk
(splits are off by default, and an archived and deleted log has nothing to
read), while a recording lives with the fight. What is kept is what the
tab's five default categories need, and no more:

- Boss: each cast of a unit the game flags as a boss (casts.py's track rule
  is not needed: a boss's cast is one line), with its target and length,
  and the END_CAST that stopped one (INTERRUPTED, with who did it); each
  boss's health as it first reaches 75, 50 and 25% in a fight; the
  stretches of 5 seconds or more in which a boss lost no health; a boss's
  death.
- Big hits: a hit on a player of 30% of their maximum health or more, the
  part a damage shield absorbed counted in (the log writes the shield's
  line just before the hit, with the attacker and the same castTrackId;
  41% of such hits are hidden otherwise), and the overkill.
- Taunts: who taunted what, and with which skill.
- Resurrections (RESURRECT and SOUL_GEM_RESURRECTION_ACCEPTED, with who
  raised whom) and each player's return from the dead, which the fight's
  time dead (pull_outcome.TimeDead) knows to the line.
- Phases: the map changing, and the game ending combat and beginning it
  again in one fight (COMBAT_RESUME_MS). A trial's end is the entry's own
  (trial_result): END_TRIAL can come seconds after the fight's last line.

Names are resolved as each event is noted, since unit ids are handed out
again in a later zone. The recorder keeps the session's events in lists,
like casts.CastRecorder, until a fight's entry is built: then the events of
its window are packed into a FightEvents, one bytes object of fixed-size
records and a table of the strings and abilities they name, immutable as
an entry must be once it crosses to the GUI's thread. The study measured
tuples at 9 to 12 times the packed size. The events before the fight's
start are then forgotten, but not when the build is of a fight the game
cut in two: the resumed entry is packed again from the same start.
"""

import struct
from collections import namedtuple
from collections.abc import Callable, Iterable, Iterator

# Event kinds, one byte each in a record
BOSS_CAST, CAST_STOPPED, BOSS_HEALTH, UNTOUCHED, BOSS_DIED = 1, 2, 3, 4, 5
HIT, TAUNT, RESURRECT, REVIVED, MAP, RESUMED = 6, 7, 8, 9, 10, 11

# A hit this share of the player's maximum health or more is kept
BIG_HIT_SHARE = 0.30
# The bosses' health marks a row names, in percent
HEALTH_MARKS = (75, 50, 25)
# A boss that lost no health this long is a stretch worth a row
UNTOUCHED_MS = 5000
# A damage shield's line comes this soon before the hit it absorbed
# (death_recap.SHIELD_PAIR_MS)
SHIELD_PAIR_MS = 100

# Flags on a record
BLOCKED = 1       # a hit the player blocked
ON_BOSS = 2       # a taunt on a boss
BY_ITSELF = 4     # a cast its own caster (or another boss) stopped
AT_PLAYER = 8     # a boss's cast aimed at a player

DAMAGE_RESULTS = frozenset({"DAMAGE", "CRITICAL_DAMAGE", "DOT_TICK", "DOT_TICK_CRITICAL",
                            "BLOCKED_DAMAGE", "FALL_DAMAGE"})
SHIELDED = "DAMAGE_SHIELDED"

# time (ms from the fight's start), kind, who (string), who's key (string),
# ability id, other (string), other's key (string), value, value2, value3,
# flags
_RECORD = struct.Struct("<iBHHIHHiiiB")

Event = namedtuple("Event", "t kind who who_key ability_id other other_key "
                            "value value2 value3 flags")


def _health(field: str) -> tuple[int, int] | None:
    """(current, maximum) from a unit state's 'current/max', None when the
    field holds no pool."""
    current, _, maximum = str(field).partition("/")
    if not maximum or not current.isdigit() or not maximum.isdigit() or maximum == "0":
        return None
    return int(current), int(maximum)


class FightEvents:
    """One fight's events, packed (see the module): immutable, read with
    records() in time order. Times are in ms from the fight's start."""

    __slots__ = ("_abilities", "_data", "_strings")

    def __init__(self, data: bytes, strings: tuple, abilities: tuple):
        self._data = data
        self._strings = strings
        # (ability id, name, icon stem) of every ability the records name
        self._abilities = abilities

    def __len__(self) -> int:
        return len(self._data) // _RECORD.size

    def __eq__(self, other) -> bool:
        return (isinstance(other, FightEvents) and self._data == other._data
                and self._strings == other._strings and self._abilities == other._abilities)

    def __hash__(self):
        return hash(self._data)

    def __repr__(self) -> str:
        return f"FightEvents({len(self)} events)"

    def records(self) -> Iterator[Event]:
        strings = self._strings
        for (t, kind, who, who_key, ability, other, other_key, value, value2, value3,
             flags) in _RECORD.iter_unpack(self._data):
            yield Event(t, kind, strings[who], strings[who_key], str(ability) if ability else "",
                        strings[other], strings[other_key], value, value2, value3, flags)

    def abilities(self) -> dict[str, tuple[str, str]]:
        """Ability id -> (name, icon stem) for the abilities the records name."""
        return {ability_id: (name, icon) for ability_id, name, icon in self._abilities}

    @property
    def nbytes(self) -> int:
        return len(self._data)


class EventRecorder:
    """The session's notable events until a fight's entry is built (see the
    module). Each note_ call takes the line's time in raw log ms and names
    already resolved; keys are the engine's: a player's record id, an
    enemy's unit id."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart."""
        # (t, kind, who, who_key, ability, other, other_key, v, v2, v3, flags)
        self._events: list[tuple] = []
        # Boss cast tracks still open: track -> (boss name, boss key, ability)
        self._boss_tracks: dict[str, tuple] = {}
        # Per boss unit: the last 'current/max' seen, the last health, the
        # last drop's time and the marks reached
        self._boss_field: dict[str, str] = {}
        self._boss_health: dict[str, int] = {}
        self._boss_drop: dict[str, int] = {}
        self._boss_marks: dict[str, set] = {}
        # Damage shields waiting for their hit: (target, source, cast) ->
        # [(time, amount), ...]
        self._shields: dict[tuple, list] = {}

    def _add(self, t, kind, who="", who_key="", ability="", other="", other_key="",
             value=0, value2=0, value3=0, flags=0) -> None:
        self._events.append((t, kind, who, who_key, ability, other, other_key,
                             value, value2, value3, flags))

    # ------------------------------------------------------------- bosses --

    def note_boss_cast(self, t: int, boss: str, boss_key: str, track: str, ability_id: str,
                       target: str, target_key: str, duration_ms: int,
                       at_player: bool = False) -> None:
        self._add(t, BOSS_CAST, boss, boss_key, ability_id, target, target_key, duration_ms,
                  flags=AT_PLAYER if at_player else 0)
        self._boss_tracks[track] = (boss, boss_key, ability_id)
        if len(self._boss_tracks) > 4096:
            # Bounded: a track is wanted only until its END_CAST, seconds on
            for old in list(self._boss_tracks)[:2048]:
                del self._boss_tracks[old]

    def holds_track(self, track: str) -> bool:
        """Whether *track* is a boss's cast still open (an END_CAST of it is
        read further)."""
        return track in self._boss_tracks

    def note_cast_end(self, t: int, track: str, reason: str, by: str, by_key: str,
                      by_boss: bool) -> None:
        """An END_CAST: one that INTERRUPTED a boss's cast is kept, with who
        stopped it (*by_boss*: the boss itself or another boss, its own
        script)."""
        held = self._boss_tracks.pop(track, None)
        if held is None or reason != "INTERRUPTED":
            return
        boss, boss_key, ability_id = held
        self._add(t, CAST_STOPPED, boss, boss_key, ability_id, by, by_key,
                  flags=BY_ITSELF if by_boss or by_key == boss_key else 0)

    def note_boss_health(self, t: int, boss: str, boss_key: str, field: str) -> None:
        """A boss's 'current/max' on a line: the marks it reaches and the
        stretches it lost no health in."""
        if self._boss_field.get(boss_key) == field:
            return
        self._boss_field[boss_key] = field
        health = _health(field)
        if health is None:
            return
        current, maximum = health
        last = self._boss_health.get(boss_key)
        self._boss_health[boss_key] = current
        if last is None:
            self._boss_drop[boss_key] = t
            return
        if current < last:
            dropped = self._boss_drop.get(boss_key)
            if dropped is not None and t - dropped >= UNTOUCHED_MS:
                self._add(dropped, UNTOUCHED, boss, boss_key, value=t - dropped)
            self._boss_drop[boss_key] = t
            marks = self._boss_marks.setdefault(boss_key, set())
            share = current * 100 / maximum
            for mark in HEALTH_MARKS:
                if share <= mark and mark not in marks and last * 100 / maximum > mark:
                    marks.add(mark)
                    self._add(t, BOSS_HEALTH, boss, boss_key, value=mark,
                              value2=round(share * 10))

    # ---------------------------------------------------------- the group --

    def note_on_player(self, t: int, result: str, fields: list, target_key: str, target: str,
                       source: str, source_key: str) -> None:
        """A combat event on the player *target_key* (a recap result): a
        damage shield's absorb waits for its hit; a hit of BIG_HIT_SHARE of
        the player's maximum health or more, absorbed part and overkill
        counted in, is kept."""
        if result == SHIELDED:
            amount = int(fields[3]) if fields[3].isdigit() else 0
            if amount:
                key = (target_key, fields[7], fields[5])
                self._shields.setdefault(key, []).append((t, amount))
                if len(self._shields) > 512:
                    for old in list(self._shields)[:256]:
                        del self._shields[old]
            return
        if result not in DAMAGE_RESULTS:
            return
        hit = int(fields[3]) if fields[3].isdigit() else 0
        overflow = int(fields[4]) if fields[4].isdigit() else 0
        absorbed = 0
        for shield_t, amount in self._shields.pop((target_key, fields[7], fields[5]), ()):
            if t - shield_t <= SHIELD_PAIR_MS:
                absorbed += amount
        health = _health(fields[18] if fields[17] != "*" else fields[8])
        if health is None:
            return
        size = hit + overflow + absorbed
        if size < BIG_HIT_SHARE * health[1]:
            return
        self._add(t, HIT, target, target_key, fields[6], source, source_key,
                  hit + overflow, health[1], absorbed,
                  BLOCKED if result == "BLOCKED_DAMAGE" else 0)

    def note_taunt(self, t: int, taunter: str, taunter_key: str, ability_id: str,
                   target: str, target_key: str, on_boss: bool) -> None:
        self._add(t, TAUNT, taunter, taunter_key, ability_id, target, target_key,
                  flags=ON_BOSS if on_boss else 0)

    def note_resurrect(self, t: int, target: str, target_key: str, by: str, by_key: str,
                       ability_id: str) -> None:
        self._add(t, RESURRECT, target, target_key, ability_id, by, by_key)

    # ------------------------------------------------------------- phases --

    def note_map(self, t: int, name: str) -> None:
        self._add(t, MAP, other=name)

    def note_resumed(self, t: int, gap_ms: int) -> None:
        self._add(t, RESUMED, value=gap_ms)

    # -------------------------------------------------------- the fight --

    def fight_events(self, start: int, end: int, revived: Iterable[tuple] = (),
                     boss_deaths: Iterable[tuple] = (),
                     ability: Callable[[str], tuple[str, str]] = lambda a: (a, "")) -> FightEvents:
        """The events from *start* to *end* (raw ms), packed, with
        *revived*: (time back, player name, player key, ms dead) from the
        fight's time dead, and *boss_deaths*: (time, boss name, boss key).
        *ability* names an ability id: (name, icon stem)."""
        events = [event for event in self._events if start <= event[0] <= end]
        events += [(back, REVIVED, name, key, "", "", "", dead_ms, 0, 0, 0)
                   for back, name, key, dead_ms in revived if start <= back <= end]
        events += [(died, BOSS_DIED, name, key, "", "", "", 0, 0, 0, 0)
                   for died, name, key in boss_deaths if start <= died <= end]
        events.sort(key=lambda event: event[0])
        strings: dict[str, int] = {"": 0}
        abilities: dict[str, tuple] = {}
        packed = bytearray()
        for (t, kind, who, who_key, ability_id, other, other_key, value, value2, value3,
             flags) in events:
            ids = [strings.setdefault(text, len(strings))
                   for text in (str(who), str(who_key), str(other), str(other_key))]
            ability_id = str(ability_id or "")
            if ability_id and ability_id not in abilities:
                abilities[ability_id] = (ability_id, *ability(ability_id))
            packed += _RECORD.pack(t - start, kind, ids[0], ids[1],
                                   int(ability_id) if ability_id.isdigit() else 0,
                                   ids[2], ids[3], int(value), int(value2), int(value3), flags)
        return FightEvents(bytes(packed), tuple(strings), tuple(abilities.values()))

    def prune_before(self, timestamp: int) -> None:
        """Forget the events before *timestamp* (the built fight's start)
        and each boss's marks: a new pull reaches them again."""
        self._events = [event for event in self._events if event[0] >= timestamp]
        self._boss_marks.clear()
        self._boss_drop.clear()
        self._boss_health.clear()
        self._boss_field.clear()
