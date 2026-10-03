"""
Death recap recording: what hit and healed a player in the seconds before
each death, for the GUI's per-player recap.

The analyzer passes every COMBAT_EVENT that lands on a player to record();
a short per-player history is kept, and note_death() turns that history into
the recap a frontend renders. Times are raw log-relative milliseconds.

How the log writes a death (checked against live trial, arena and dungeon
logs):

- The dying unit's event is DIED, or KILLING_BLOW when the killer is a player
  (friendly fire, PvP). Its source and ability name the killer.
- The killing blow's own damage line usually comes *after* that event, 0-2 ms
  later, carrying the overkill in the overflow field.
- hitValue is what actually reached (or restored) health; the target's unit
  state on the line is the state after the event.
- DAMAGE_SHIELDED lines come just before the hit they absorbed, with the
  attacker as source, the same castTrackId, and the shield as the ability.
  Several shields can soak one hit, and the death event can sit between the
  shields and the hit.
"""

from collections import deque
from typing import Callable, Dict, List, Optional, Tuple

# Chronology kept before each death
RECAP_WINDOW_MS = 5000

# Events on the dead player this soon after the death event belong to it: the
# killing blow and anything landing in the same instant. Later hits are on
# the corpse.
KILLING_BLOW_GRACE_MS = 100

# A shield is folded into the hit it absorbed only when the two are this close
SHIELD_PAIR_MS = 100

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
_HEAL_RESULTS = frozenset(r for r, kind in _KINDS.items() if kind == "heal")

# Indices into a COMBAT_EVENT's fields (after the time offset and line type):
# actionResult, damageType, powerType, hitValue, overflow, castTrackId,
# abilityId, then the 10-field source unit state and the target's (or '*')
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


class DeathRecapRecorder:
    """Keeps each player's recent combat events and builds death recaps."""

    def __init__(self, resolve_unit: Callable[[str], str],
                 resolve_ability: Callable[[str], Tuple[str, str]]):
        # unit id -> display name ('' when the log names no unit);
        # ability id -> (name, icon stem)
        self._resolve_unit = resolve_unit
        self._resolve_ability = resolve_ability
        # unit id -> events of the last RECAP_WINDOW_MS, oldest first
        self._recent: Dict[str, deque] = {}
        # unit id -> (recap, its raw events, death time) while the killing
        # blow may still arrive
        self._open: Dict[str, tuple] = {}

    def reset(self) -> None:
        """Drop all state (new log session or zone: unit ids start over)."""
        self._recent.clear()
        self._open.clear()

    def record(self, timestamp_ms: int, fields: List[str], target_id: str) -> None:
        """Note one COMBAT_EVENT whose result is in RECAP_RESULTS and whose
        target is the player *target_id*."""
        result = fields[0]
        if fields[_HIT] == "0" and result in _HEAL_RESULTS:
            return  # pure overheal: health did not move
        health_at = _TARGET_HEALTH if fields[_TARGET] != "*" else _SOURCE_HEALTH
        event = (timestamp_ms, result, fields[_HIT], fields[_OVERFLOW],
                 fields[_CAST], fields[_ABILITY], fields[_SOURCE], fields[health_at])

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
        cutoff = timestamp_ms - RECAP_WINDOW_MS
        while recent[0][0] < cutoff:
            recent.popleft()

    def note_death(self, unit_id: str, timestamp_ms: int, fields: List[str]) -> dict:
        """Recap for the player *unit_id*, whose DIED/KILLING_BLOW event has
        *fields*. The returned dict keeps filling for KILLING_BLOW_GRACE_MS as
        the killing blow is logged.
        """
        cutoff = timestamp_ms - RECAP_WINDOW_MS
        events = [e for e in self._recent.pop(unit_id, ()) if e[0] >= cutoff]
        ability_id = fields[_ABILITY] if len(fields) > _ABILITY else ""
        source_id = fields[_SOURCE] if len(fields) > _SOURCE else "0"
        self_inflicted = len(fields) <= _TARGET or fields[_TARGET] == "*"
        health_at = _SOURCE_HEALTH if self_inflicted else _TARGET_HEALTH
        ability, icon = self._resolve_ability(ability_id)
        recap = {
            "killer": self._resolve_unit(source_id),
            "ability": ability,
            "ability_id": ability_id,
            "icon": icon,
            "max_health": _health(fields[health_at])[1] if len(fields) > health_at else 0,
            "events": [],
        }
        self._fill(recap, events, timestamp_ms)
        self._open[unit_id] = (recap, events, timestamp_ms)
        return recap

    def _fill(self, recap: dict, events: list, died_ms: int) -> None:
        """(Re)build the recap's rows from its raw events."""
        rows = self._rows(events, died_ms)
        if not recap["killer"]:
            # A death event with no source unit (seen when the blow also ends
            # the fight): the hit by the same ability names the killer
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
        for (timestamp_ms, result, hit, overflow,
             cast_id, ability_id, source_id, health) in events:
            kind = _KINDS[result]
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
            }
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
