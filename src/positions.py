"""
Where the group stood in each fight, for the fight pane's map (engine side,
no Qt). Issue #148.

Design: every unit state on a COMBAT_EVENT, EFFECT_CHANGED, BEGIN_CAST or
HEALTH_REGEN line ends with the unit's x, y and heading, and the x and y are
fractions of the map the logging player is on: the last MAP_CHANGED's, for
every unit. So when that player's map changes, everyone's coordinates jump
to the new map's frame. In Sunspire on 2026-09-23 a trash pull ran from the
Shrine of Jone Vestibule into the Temple Grounds, and at the MAP_CHANGED all
23 units seen on both sides moved by a median 0.63 of the map's width, some
to a y of 1.19, past the map's edge. Kyne's Aegis's Lord Falgravn changes
between his three floor maps up to five times in a fight, and there the
units moved a median 0.004 to 0.021: the floors share one frame. So a
position belongs to the map that was current when its line was written,
and each one is kept with that map. Sanity's Edge and Dreadsail Reef give
every one of their sub-maps the zone's name, so a map is known by its
texture path, never by its name.

The lines just after a zone's MAP_CHANGED can carry other coordinates
altogether while the zone loads (212.9151, -195.2606 in Lucent Citadel on
2026-10-11), so a position outside VALID_RANGE is not a position on the
map. One a little past the edge, like Sunspire's 1.19, is clamped to it.

A unit's position is only written when it appears on a line. Each line's
unit states are kept as their raw strings, the latest per unit id, which
keeps the cost per line to a dictionary write. Once a second of log time
(SAMPLE_MS) during a fight, each group member's latest position is parsed
and kept as a sample, filed under its map. A member silent for more than
STALE_MS is left out of that second rather than held in place, and so is
one whose latest health is 0: a body is not where the group stood, and a
resurrected player's lines carry their health again. Sampling by time and
not by line keeps a player with many damage-over-time ticks from counting
for more than one who has few.

A sample is two numbers from 0 to SCALE, x and y as fractions of the map in
steps of 1/SCALE (the log writes four decimals), held in arrays: a fight of
twelve players over five minutes is some 3,600 samples, 14 KB.
"""

from array import array
from bisect import bisect_left, bisect_right
from collections.abc import Iterable

SAMPLE_MS = 1000  # one sample per group member per second of the fight
STALE_MS = 3000  # a position older than this is not where the unit is now
SCALE = 10000  # a stored coordinate is the fraction of the map times this
# A coordinate outside this is not a place on the map (see above); inside it
# but past an edge, it is clamped to the edge
VALID_RANGE = (-0.5, 1.5)


class PositionRecorder:
    """The group's positions over a BEGIN_LOG session, sampled once a
    second while a fight is on, until a fight's entry takes them."""

    def __init__(self):
        # The maps seen this session, (texture path in lower case, map id,
        # name), in the order first seen; a sample names its map by index
        self._maps: list[tuple[str, str, str]] = []
        self._map_index: dict[str, int] = {}
        self._current = -1  # the logging player's map; -1 before any MAP_CHANGED
        # unit id -> (x, y, time, map, health) of its latest unit state,
        # the strings as the line wrote them
        self._latest: dict[str, tuple[str, str, int, int, str]] = {}
        self.active = False  # sampling: between BEGIN_COMBAT and END_COMBAT
        self.next_tick = 0  # log time of the next sample
        self._times = array('q')
        self._map_of = array('H')
        self._xy = array('H')  # x, y of each sample, interleaved

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart and every map is
        named again."""
        self._maps.clear()
        self._map_index.clear()
        self._current = -1
        self._latest.clear()
        self.active = False
        self.next_tick = 0
        self._times = array('q')
        self._map_of = array('H')
        self._xy = array('H')

    def zone_changed(self) -> None:
        """Unit ids are handed out afresh in each zone, and the zone's own
        MAP_CHANGED follows."""
        self._latest.clear()
        self._current = -1

    def map_changed(self, map_id: str, name: str, path: str) -> None:
        """A MAP_CHANGED: positions from here on are fractions of this map."""
        key = (path or "").strip().lower()
        if not key:
            self._current = -1
            return
        index = self._map_index.get(key)
        if index is None:
            index = len(self._maps)
            self._maps.append((key, str(map_id or ""), str(name or "")))
            self._map_index[key] = index
        self._current = index

    def note(self, unit_id: str, health: str, x: str, y: str, timestamp: int) -> None:
        """A unit state on a line: the unit's latest position, kept raw."""
        self._latest[unit_id] = (x, y, timestamp, self._current, health)

    def begin_combat(self, timestamp: int) -> None:
        """BEGIN_COMBAT: the first sample is now."""
        self.active = True
        self.next_tick = timestamp

    def resume(self) -> None:
        """The fight the game cut in two carries on (the engine's
        COMBAT_RESUME_MS): sampling starts again, and the seconds between
        the two lines have none."""
        self.active = True

    def end_combat(self, timestamp: int) -> None:
        """END_COMBAT: the seconds up to it are sampled, then no more."""
        self.active = False

    def sample(self, timestamp: int, units: Iterable[tuple[str, ...]]) -> None:
        """Take the samples due up to *timestamp*, before its line's unit
        states are noted. *units* holds one tuple of unit ids per group
        member (a player back on a new unit id has several); the freshest
        of them is the member's position."""
        tick = self.next_tick
        if tick > timestamp:
            return
        members = list(units)
        # Every position noted so far is older than the first tick due (a
        # line at or past it would have taken it), so STALE_MS after that
        # tick all of them are stale, and the ticks of a long lull up to
        # this line are skipped
        fresh_until = tick + STALE_MS
        while tick <= timestamp and tick <= fresh_until:
            self._take(tick, members)
            tick += SAMPLE_MS
        if tick <= timestamp:
            tick += ((timestamp - tick) // SAMPLE_MS + 1) * SAMPLE_MS
        self.next_tick = tick

    def _take(self, tick: int, members: list[tuple[str, ...]]) -> None:
        latest = self._latest
        low, high = VALID_RANGE
        for unit_ids in members:
            best = None
            for unit_id in unit_ids:
                state = latest.get(unit_id)
                if state is not None and (best is None or state[2] > best[2]):
                    best = state
            if best is None or tick - best[2] > STALE_MS:
                continue
            x_text, y_text, _at, map_index, health = best
            if map_index < 0 or health.startswith("0/"):
                continue
            try:
                x, y = float(x_text), float(y_text)
            except ValueError:
                continue
            if not (low <= x <= high and low <= y <= high) or (x == 0.0 and y == 0.0):
                continue
            self._times.append(tick)
            self._map_of.append(map_index)
            self._xy.append(round(min(max(x, 0.0), 1.0) * SCALE))
            self._xy.append(round(min(max(y, 0.0), 1.0) * SCALE))

    def fight_maps(self, start: int, end: int) -> list[dict]:
        """The samples taken from *start* to *end*, one dict per map in the
        order the group first stood on it: path (the texture path in lower
        case), map_id, name, xy (x, y of each sample, interleaved, in steps
        of 1/SCALE), seconds (the seconds with a sample on the map) and
        first_s (its first sample, in seconds from *start*)."""
        first = bisect_left(self._times, start)
        last = bisect_right(self._times, end)
        maps: dict[int, dict] = {}
        ticks: dict[int, set[int]] = {}
        for i in range(first, last):
            index = self._map_of[i]
            record = maps.get(index)
            if record is None:
                path, map_id, name = self._maps[index]
                record = maps[index] = {
                    'path': path, 'map_id': map_id, 'name': name, 'xy': array('H'),
                    'seconds': 0, 'first_s': (self._times[i] - start) / 1000.0}
                ticks[index] = set()
            record['xy'].append(self._xy[2 * i])
            record['xy'].append(self._xy[2 * i + 1])
            ticks[index].add(self._times[i])
        for index, record in maps.items():
            record['seconds'] = len(ticks[index])
        return list(maps.values())

    def prune_before(self, timestamp: int) -> None:
        """Forget the samples taken before *timestamp*."""
        cut = bisect_left(self._times, timestamp)
        if cut:
            self._times = self._times[cut:]
            self._map_of = self._map_of[cut:]
            self._xy = self._xy[2 * cut:]
