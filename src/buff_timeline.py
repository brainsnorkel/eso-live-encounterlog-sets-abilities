"""
EXPERIMENTAL buff/debuff timeline recording (buff-timeline spec).

Records the active intervals of a handful of raid-defining effects with
cast/receive attribution, so the GUI can draw a compact per-fight timeline
strip. Recording is opt-in (`experimental.buff_timeline`); when the analyzer's
gate is off, record() is never called and nothing is retained.

Interval times are raw log-relative milliseconds; snapshot_fight() clips them
to a fight's [start, end] window and rebases them to fight-relative ms.
"""

from collections import defaultdict
from typing import Callable, Dict, List, Optional

# Effect name -> ability IDs observed in live logs. A named buff can be
# applied by several distinct ability IDs (different sources/sets).
TRACKED_TIMELINE_EFFECTS: Dict[str, set] = {
    "Major Slayer": {"93109"},
    "Major Force": {"61747"},
    "Major Courage": {"109966"},
    # 61745 is the primary aura in live logs; 263306/36973 are alternate
    # applicators; 62195 kept for older logs
    "Major Berserk": {"61745", "263306", "36973", "62195"},
    "Major Vulnerability": {"106754", "122389", "167061"},
}

# Adjacent intervals for the same (source, target) closer than this are one
# logical application (UPDATED refreshes can produce FADED/GAINED flickers).
MERGE_GAP_MS = 500

# Runaway guard: a very long fight can't grow an effect's list past this.
MAX_INTERVALS_PER_EFFECT = 2000


class BuffTimelineRecorder:
    """Accumulates effect intervals from EFFECT_CHANGED events."""

    def __init__(self):
        self._id_to_effect: Dict[str, str] = {
            ability_id: effect
            for effect, ids in TRACKED_TIMELINE_EFFECTS.items()
            for ability_id in ids
        }
        # (effect, target_id) -> [start_ms, source_id]
        self._open: Dict[tuple, list] = {}
        # effect -> [[start_ms, end_ms, source_id, target_id], ...] (closed)
        self._closed: Dict[str, List[list]] = defaultdict(list)

    def reset(self) -> None:
        """Drop all state (a new BEGIN_LOG restarts the ms timestamp domain)."""
        self._open.clear()
        self._closed.clear()

    def record(self, effect_type: str, ability_id: str,
               source_id: str, target_id: str, timestamp_ms: int) -> None:
        effect = self._id_to_effect.get(str(ability_id))
        if effect is None:
            return
        key = (effect, str(target_id))
        if effect_type in ("GAINED", "UPDATED"):
            # UPDATED without an open interval means we attached mid-effect
            # (or a stack refresh after a missed GAINED): open one now.
            self._open.setdefault(key, [timestamp_ms, str(source_id)])
        elif effect_type == "FADED":
            opened = self._open.pop(key, None)
            if opened is not None:
                self._append(effect, opened[0], timestamp_ms, opened[1], key[1])

    def _append(self, effect: str, start: int, end: int,
                source_id: str, target_id: str) -> None:
        if end <= start:
            return
        intervals = self._closed[effect]
        if intervals:
            last = intervals[-1]
            if (last[2] == source_id and last[3] == target_id
                    and 0 <= start - last[1] <= MERGE_GAP_MS):
                last[1] = max(last[1], end)
                return
        if len(intervals) >= MAX_INTERVALS_PER_EFFECT:
            intervals.pop(0)
        intervals.append([start, end, source_id, target_id])

    def snapshot_fight(self, fight_start_ms: int, fight_end_ms: int,
                       resolve_name: Callable[[str], str]) -> Optional[dict]:
        """Timeline data for one fight window, or None if nothing overlaps.

        Returns {'duration_ms': int, 'effects': {effect: [interval, ...]}}
        where each interval is {'start_ms', 'end_ms' (fight-relative),
        'source', 'target' (display names)}.
        """
        if fight_end_ms <= fight_start_ms:
            return None

        effects: Dict[str, List[dict]] = {}
        for effect in TRACKED_TIMELINE_EFFECTS:
            rows = []
            candidates = list(self._closed.get(effect, []))
            candidates.extend(
                [start, fight_end_ms, source, key[1]]
                for key, (start, source) in self._open.items()
                if key[0] == effect
            )
            for start, end, source_id, target_id in candidates:
                if end <= fight_start_ms or start >= fight_end_ms:
                    continue
                rows.append({
                    "start_ms": max(start, fight_start_ms) - fight_start_ms,
                    "end_ms": min(end, fight_end_ms) - fight_start_ms,
                    "source": resolve_name(source_id),
                    "target": resolve_name(target_id),
                })
            if rows:
                rows.sort(key=lambda r: (r["start_ms"], r["end_ms"]))
                effects[effect] = rows

        if not effects:
            return None
        return {"duration_ms": fight_end_ms - fight_start_ms, "effects": effects}

    def prune_before(self, timestamp_ms: int) -> None:
        """Free closed intervals that ended before *timestamp_ms*."""
        for effect in list(self._closed):
            kept = [iv for iv in self._closed[effect] if iv[1] > timestamp_ms]
            if kept:
                self._closed[effect] = kept
            else:
                del self._closed[effect]


def extract_effect_fields(fields: List[str]) -> Optional[tuple]:
    """(effect_type, ability_id, source_id, target_id) from EFFECT_CHANGED
    entry fields, or None if the shape is unexpected.

    Layout (after line offset + event type): [0] changeType, [3] abilityId,
    [4] first field of the 10-field source unit state, [14] '*' (self-target)
    or the first field of the target unit state.
    """
    if len(fields) < 5:
        return None
    effect_type = fields[0]
    ability_id = str(fields[3])
    source_id = str(fields[4])
    target_id = source_id
    if len(fields) > 14 and fields[14] != "*":
        target_id = str(fields[14])
    return effect_type, ability_id, source_id, target_id
