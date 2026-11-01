"""
Death recap recording: what hit and healed a player in the seconds before
each death, for the GUI's per-player recap.

The analyzer passes every COMBAT_EVENT whose target is a player to record();
a short per-player history is kept, and note_death() turns that history into
the recap a frontend renders. Times are raw log-relative milliseconds.

How the log writes a death (checked against live trial, arena and dungeon
logs):

- The dying unit's event is DIED, or KILLING_BLOW when the killer is a player
  (friendly fire, PvP). Its source and ability name the killer.
- A fall into lava, off a ledge or out of the map is one KILLED_BY_SUBZONE
  line and nothing else (issue #184): no DIED within ten seconds either side,
  the source unit 0 with an empty state, ability and cast track 0, the dying
  player in the target block at 0 health. Until #184 the engine did not
  count it, so the death had no recap, no time dead and the pull read as if
  nobody died. The recap names no killer, gives FALL_DEATH as what killed
  and carries cause FALL_CAUSE. Only a player's counts: the logs hold none
  on an enemy, and one there would read as the group's kill. Every one of the 18 in the maintainer's logs (2025-10 to 2026-11)
  was the writer's own: 17 falls on Sunspire's Temple Grounds, all outside a
  fight, and one into Rahdgarak's lava in Vateshran Hollows, 26 ms before
  END_COMBAT. A FALLING line came before only that last one, and FALLING
  lines carry whatever ability the player had (Bash, a fire or shock id),
  so they make no recap row.
- The killing blow's own damage line usually comes *after* that event, 0-2 ms
  later, carrying the overkill in the overflow field.
- hitValue is what actually reached (or restored) health; the target's unit
  state on the line is the state after the event.
- DAMAGE_SHIELDED lines come just before the hit they absorbed, with the
  attacker as source, the same castTrackId, and the shield as the ability.
  Several shields can soak one hit, and the death event can sit between the
  shields and the hit.

Each row also carries the kinds of the hit (damage_kinds, issue #73): its
damage type, and whether it was an area hit, read from the cast index the
analyzer shares with the recorder (a cast that struck two or more units),
with the rule that decided and the number of players the cast struck. Rows
are classed when the recap is built or refilled, and once more when the
fight ends (refresh_fight), so a ground effect that reached a second player
seconds after the death still reads as area. Pure overheals (a heal line
whose hit value is zero) are kept in the window for the recap's overheal
sum but never become rows.

The window is a setting (issue #95): 5 seconds by default, up to 10, read
from the config when the engine is built (app_startup), so a Settings save,
which rebuilds the engine and replays the session, rebuilds the fights
already listed with the new window. Each recap records the window it was
built with ('window_ms'), so a frontend names the right number of seconds
for a fight recorded under another setting, and a recap from before the key
existed reads as the old fixed five.
"""

from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

from damage_kinds import area_of

# Chronology kept before each death: the default, and what Settings allows
DEFAULT_WINDOW_S = 5
MIN_WINDOW_S, MAX_WINDOW_S = 5, 10
RECAP_WINDOW_MS = DEFAULT_WINDOW_S * 1000

# Events on the dead player this soon after the death event belong to it: the
# killing blow and anything arriving in the same instant. Later hits are on
# the corpse.
KILLING_BLOW_GRACE_MS = 100

# A shield is folded into the hit it absorbed only when the two are this close
SHIELD_PAIR_MS = 100

# How the log writes a unit's death (the analyzer's death branch): DIED,
# DIED_XP (an enemy's death that grants experience), KILLING_BLOW (a player
# killed by a player) and a fall's KILLED_BY_SUBZONE (see the module docstring)
SUBZONE_DEATH = "KILLED_BY_SUBZONE"
DEATH_RESULTS = frozenset({"DIED", "DIED_XP", "KILLING_BLOW", SUBZONE_DEATH})
# What killed, for a fall: the recap's ability text. It has to read in every
# sentence that names a killer ('Killed by …', 'First death: @x to …',
# 'Killers: … 2'), with no brackets, which those sentences use for the
# killer after the ability ('Slap (Sharpfang)')
FALL_DEATH = "a fall or lava"
# The recap's 'cause' for a fall, the field code tests rather than the text
FALL_CAUSE = "fall"

# actionResult -> kind of recap row
_KINDS: Dict[str, str] = {
    "DAMAGE": "damage",
    "CRITICAL_DAMAGE": "damage",
    "DOT_TICK": "damage",
    "DOT_TICK_CRITICAL": "damage",
    "BLOCKED_DAMAGE": "damage",
    "FALL_DAMAGE": "damage",
    "DODGED": "avoided",
    "MISS": "avoided",
    "HEAL": "heal",
    "CRITICAL_HEAL": "heal",
    "HOT_TICK": "heal",
    "HOT_TICK_CRITICAL": "heal",
    "DAMAGE_SHIELDED": "absorbed",
    "HEAL_ABSORBED": "heal_absorbed",
}

# The analyzer checks this before paying for anything else
RECAP_RESULTS = frozenset(_KINDS)
# How the log writes a heal that restored health (the analyzer totals these
# for the role heuristic too)
HEAL_RESULTS = frozenset(r for r, kind in _KINDS.items() if kind == "heal")

# Indices into a COMBAT_EVENT's fields (after the time offset and line type):
# actionResult, damageType, powerType, hitValue, overflow, castTrackId,
# abilityId, then the 10-field source unit state and the target's (or '*')
_DAMAGE_TYPE = 1
_HIT, _OVERFLOW, _CAST, _ABILITY, _SOURCE = 3, 4, 5, 6, 7
_SOURCE_HEALTH, _TARGET, _TARGET_HEALTH = 8, 17, 18


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _health(value) -> Tuple[int, int]:
    """(current, max) from a unit state's 'current/max' health field."""
    current, _, maximum = str(value).partition("/")
    return _int(current), _int(maximum)


def recap_window_s(value) -> int:
    """The recap window in seconds from a config value: an integer held
    to MIN_WINDOW_S..MAX_WINDOW_S, the default for anything that is not a
    number."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_WINDOW_S
    return max(MIN_WINDOW_S, min(MAX_WINDOW_S, seconds))


class DeathRecapRecorder:
    """Keeps each player's recent combat events and builds death recaps."""

    def __init__(self, resolve_unit: Callable[[str], str],
                 resolve_ability: Callable[[str], Tuple[str, str]], cast_index=None,
                 window_ms: int = RECAP_WINDOW_MS):
        # unit id -> display name ('' when the log names no unit);
        # ability id -> (name, icon stem)
        self._resolve_unit = resolve_unit
        self._resolve_ability = resolve_ability
        # The analyzer's damage_kinds.CastIndex, which tells an area hit
        # from a single one; None classes every hit as single
        self.cast_index = cast_index
        # How far back a recap reaches (the Settings value, app_startup);
        # set before the lines are fed, since it bounds the history kept
        self.window_ms = int(window_ms)
        # unit id -> events of the last window_ms, oldest first
        self._recent: Dict[str, deque] = {}
        # unit id -> (recap, its raw events, death time) while the killing
        # blow may still arrive
        self._open: Dict[str, tuple] = {}
        # (recap, its raw events, death time) of this fight's deaths, for
        # the reclassing at the fight's end (refresh_fight)
        self._fight: List[tuple] = []

    def reset(self) -> None:
        """Drop all state (new log session or zone: unit ids start over)."""
        self._recent.clear()
        self._open.clear()
        self._fight.clear()

    def new_fight(self) -> None:
        """A new fight begins: the last fight's recaps are final."""
        self._fight.clear()

    def refresh_fight(self) -> None:
        """Class this fight's recap rows again with what the cast index
        knows now that the fight is over."""
        for recap, events, died_ms in self._fight:
            self._fill(recap, events, died_ms)

    def record(self, timestamp_ms: int, fields: List[str], target_id: str,
               player_source: bool = False) -> None:
        """Note one COMBAT_EVENT whose result is in RECAP_RESULTS and whose
        target is the player *target_id*; *player_source* says a player or
        a player's pet dealt it (the area rule's table applies then)."""
        result = fields[0]
        health_at = _TARGET_HEALTH if fields[_TARGET] != "*" else _SOURCE_HEALTH
        event = (timestamp_ms, result, fields[_HIT], fields[_OVERFLOW],
                 fields[_CAST], fields[_ABILITY], fields[_SOURCE], fields[health_at],
                 fields[_DAMAGE_TYPE], player_source)

        opened = self._open.get(target_id)
        if opened is not None:
            recap, events, died_ms = opened
            if timestamp_ms - died_ms <= KILLING_BLOW_GRACE_MS:
                events.append(event)
                self._fill(recap, events, died_ms)
                return
            del self._open[target_id]

        recent = self._recent.get(target_id)
        if recent is None:
            recent = self._recent[target_id] = deque()
        recent.append(event)
        cutoff = timestamp_ms - self.window_ms
        while recent[0][0] < cutoff:
            recent.popleft()

    def note_death(self, unit_id: str, timestamp_ms: int, fields: List[str]) -> dict:
        """Recap for the player *unit_id*, whose DIED/KILLING_BLOW event has
        *fields* (or KILLED_BY_SUBZONE, a fall). The returned dict keeps
        filling for KILLING_BLOW_GRACE_MS as the killing blow is logged.
        """
        cutoff = timestamp_ms - self.window_ms
        events = [e for e in self._recent.pop(unit_id, ()) if e[0] >= cutoff]
        ability_id = fields[_ABILITY] if len(fields) > _ABILITY else ""
        source_id = fields[_SOURCE] if len(fields) > _SOURCE else "0"
        self_inflicted = len(fields) <= _TARGET or fields[_TARGET] == "*"
        health_at = _SOURCE_HEALTH if self_inflicted else _TARGET_HEALTH
        fall = bool(fields) and fields[0] == SUBZONE_DEATH
        if fall:
            # A fall names no killer and no ability (ids 0)
            ability, icon = FALL_DEATH, ""
        else:
            ability, icon = self._resolve_ability(ability_id)
        recap = {
            "killer": self._resolve_unit(source_id),
            "ability": ability,
            "ability_id": ability_id,
            "icon": icon,
            # Why the player died where the line says more than its killer:
            # FALL_CAUSE for a fall, else empty
            "cause": FALL_CAUSE if fall else "",
            "max_health": _health(fields[health_at])[1] if len(fields) > health_at else 0,
            "window_ms": self.window_ms,
            "overheal": 0,
            "events": [],
        }
        self._fill(recap, events, timestamp_ms)
        self._open[unit_id] = (recap, events, timestamp_ms)
        self._fight.append((recap, events, timestamp_ms))
        return recap

    def _fill(self, recap: dict, events: list, died_ms: int) -> None:
        """(Re)build the recap's rows from its raw events, and sum the
        window's overheal (the pure overheals included, which are no rows)."""
        rows = self._rows(events, died_ms)
        recap["overheal"] = sum(_int(event[3]) for event in events
                                if event[1] in HEAL_RESULTS)
        if not recap["killer"] and recap.get("cause") != FALL_CAUSE:
            # A death event with no source unit (seen when the blow also ends
            # the fight): the hit by the same ability names the killer. Not
            # for a fall, which has no killer whatever hit the player before
            for row in reversed(rows):
                if row["kind"] == "damage" and row["ability_id"] == recap["ability_id"]:
                    recap["killer"] = row["source"]
                    break
        recap["events"] = rows

    def _rows(self, events: list, died_ms: int) -> List[dict]:
        rows: List[Optional[dict]] = []
        # (source, castTrackId) -> (time, index into rows) of shields still
        # waiting for the hit they absorbed
        waiting: Dict[tuple, list] = {}
        for (timestamp_ms, result, hit, overflow, cast_id, ability_id, source_id,
             health, damage_type, player_source) in events:
            kind = _KINDS[result]
            if kind == "heal" and hit == "0":
                continue  # pure overheal: health did not move (summed by _fill)
            ability, icon = self._resolve_ability(ability_id)
            current, maximum = _health(health)
            row = {
                "offset_ms": timestamp_ms - died_ms,
                "kind": kind,
                "result": result,
                "source": self._resolve_unit(source_id),
                "ability": ability,
                "ability_id": ability_id,
                "icon": icon,
                "amount": _int(hit),
                "overflow": _int(overflow),
                "absorbed": 0,
                "shields": [],
                "health": current,
                "max_health": maximum,
                "damage_type": damage_type,
                "area": False,
                "area_rule": "",
                "targets_hit": 0,
            }
            if kind == "damage" and result != "FALL_DAMAGE":
                area, rule, targets = area_of(self.cast_index, source_id, cast_id,
                                              ability_id, player_source)
                row["area"], row["area_rule"], row["targets_hit"] = area, rule, targets
            key = (source_id, cast_id)
            if kind == "absorbed":
                waiting.setdefault(key, []).append((timestamp_ms, len(rows)))
            elif kind == "damage":
                for shield_ms, index in waiting.pop(key, ()):
                    shield = rows[index]
                    if shield is None or timestamp_ms - shield_ms > SHIELD_PAIR_MS:
                        continue
                    row["absorbed"] += shield["amount"]
                    if shield["ability"] not in row["shields"]:
                        row["shields"].append(shield["ability"])
                    rows[index] = None
            rows.append(row)
        return [row for row in rows if row is not None]
