"""
Damage accounting per fight, the way Combat Metrics does it.

Combat Metrics (the LibCombat library behind it) is the addon ESO players
quote dps from, so this app's figures follow its definitions. The parts
that matter, read from LibCombat.lua and CombatMetrics.lua (October 2026):

- **DPS time, not combat time.** A fight's ``dpstime`` is the time between
  the player's first and last damage event, floored at one second
  (``max((dpsend - dpsstart) / 1000, 1)``), and every dps figure divides by
  it: ``DPSOut = damageOutTotal / dpstime``. The combat time (combat state
  on to off) is kept beside it and shown, but divides nothing. The live
  number during a fight is the same quotient, so it does not sink while
  the player stands still: ``dpsend`` is the last hit, not now. Here the
  fight time stays what the history line and header show (BEGIN_COMBAT to
  END_COMBAT, with the game's cuts healed, see COMBAT_RESUME_MS), and each
  dps figure divides by a dps time of its own: a player's by the span of
  their own hits, the group's by the span of the group's, a boss figure by
  the span of the hits on the bosses. That is what each player's own
  Combat Metrics shows them, and what they post in chat.
- **Boss dps** divides the damage dealt to the boss units by the span of the
  hits on those units (``GetBossTargetDamage``: ``bossTime`` from the boss
  units' own first and last event), and falls back to the fight's dps time
  only when that span is empty.
- **What counts** is the six results in DAMAGE_RESULTS (esolog_tail), from
  the player and the player's pets, to any unit that is not a player pet.
  Overkill is dropped: LibCombat overwrites the game's overflow value with
  the shield amount it pairs to the hit. A damage shield's absorb is added
  to the hit it absorbed (``DAMAGE_SHIELDED`` events buffered and matched on
  source and target within 100 ms); the encounter log writes the absorb as
  its own line, so summing those lines is the same total.
- **Group dps** in Combat Metrics is the group's damage over the *logging
  player's* dps time (``UpdateGrpStats``: ``groupDamageOut / self.dpstime``),
  a limit of an addon that sees one client's combat state. The log sees
  every player's hits, so here the group's dps time is the span of the
  group's own hits, which is what that quotient means.
- **The breakdown by ability** (``ProcessLogDamage`` / ``AccumulateStats``)
  keys on the ability id and whether a pet cast it, and keeps per key the
  damage by result (normal, critical, blocked, shielded), the hit counts by
  result, and the largest and smallest hit; a row's dps is its damage over
  the fight's dps time, its crit rate is critical hits over hits, and its
  average is damage over hits. The window here keeps the same figures per
  player, for all targets and for the boss units alone, and the damage per
  target unit with its own first-to-last span ("the damage per second
  between your first and your last hit to that target").
- **The graph** (``CombatMetricsUI.lua``, ``Smoothed`` and ``Total``) works
  from the damage summed into one bucket per second of the fight
  (``calculated.graph``, filled by ``ProcessLogDamage``). Its dps curve is a
  centred moving average over ``SmoothWindow`` seconds (5 by default): a
  point at ``t + w/2`` with the mean of the buckets ``t .. t+w-1``, the
  first and last points carried to the fight's edges. Its total curve is
  the live figure as it stood: the damage so far over the dps time so far
  (``sum / (min(dpsend, t) - dpsstart)``), from half a window after the
  first hit on. The graph window draws both (smoothed_dps, running_dps),
  for the group and for each player, from the same per-second buckets
  (PlayerDamage.buckets, FightDamage.buckets).

Differences left in place, on purpose: a hit a shield absorbed in full is
written as a DAMAGE line of value 0 beside its DAMAGE_SHIELDED line (two
thirds of the shield lines in two logs of 2026; the rest sit beside a
partial hit or alone), and the engine drops every zero hit, so such a hit
counts as absorbed damage but not as a hit where Combat Metrics counts it
as one; and dps figures are kept as floats where Combat Metrics rounds to
the integer.

Measured on 113 split logs of 2026 (1,941 fights with damage, 564 with a
boss), dividing by the dps time instead of the fight time raises the group's
dps by a median 1.0% in boss fights of a minute or more (p90 5.9%), each
player's own dps by a median 5.8% (p90 41%) and their boss dps by a median
9.7% (p90 75%): the group's first hit comes a median 0.5 s after
BEGIN_COMBAT and END_COMBAT a median 0.5 s (p90 6 s) after its last, and a
player's own span is more than 10% shorter than the group's in 29% of
player-fights (died, arrived late, stopped hitting). What the engine does
not count stays negligible: hits on units the log never added 0.07% of all
damage, on non-hostile units 0.00%, in the two seconds before BEGIN_COMBAT
0.04%, in the 1.3 s after END_COMBAT 0.02%.
"""

from array import array
from collections import Counter
from typing import Callable, Dict, List, Optional, Tuple

from damage_kinds import classify

# LibCombat: dpstime = zo_max((dpsend - dpsstart) / 1000, 1)
MIN_DPS_TIME_S = 1.0

CRIT_RESULTS = frozenset(('CRITICAL_DAMAGE', 'DOT_TICK_CRITICAL'))
TICK_RESULTS = frozenset(('DOT_TICK', 'DOT_TICK_CRITICAL'))
SHIELDED = 'DAMAGE_SHIELDED'
BLOCKED = 'BLOCKED_DAMAGE'


def dps_time_s(span_ms: int) -> float:
    """A dps time: the span in seconds, floored at a second like LibCombat.

    A span of 0 (one hit, or none) is a second, so a single hit reads as
    its own damage per second rather than infinity."""
    return max(span_ms / 1000.0, MIN_DPS_TIME_S)


def dps(damage: int, span_ms: int) -> float:
    """Damage per second over the dps time of *span_ms*; 0 for no damage."""
    if damage <= 0:
        return 0.0
    return damage / dps_time_s(span_ms)


def _bucket(buckets: Dict[int, int], ts: int, hit: int) -> None:
    """Add a hit to the bucket of its log second."""
    second = ts // 1000
    buckets[second] = buckets.get(second, 0) + hit


def series_of(buckets: Dict[int, int], origin_ms: Optional[int] = None) -> List[List[float]]:
    """The buckets as a series for a fight entry: [[t, damage], ...] in time
    order, t the bucket's start in seconds into the fight (from *origin_ms*,
    the fight's start; log seconds when none), each bucket a second long."""
    origin = (origin_ms or 0) / 1000.0
    return sorted([float(second) - origin, damage] for second, damage in buckets.items())


class Series:
    """A series_of result as a fight entry keeps it (issue #110): the same
    [t, damage] pairs, read the same way (iterated, indexed, compared with
    the list form), held in two arrays. A pair as a list of a float and an
    int is about 124 bytes; here it is 16, and the values are the same
    (doubles and 64-bit integers). Every player has two series per fight,
    a second each, which was a ninth of the per-player data of a trial
    night. Damage that is not a whole number keeps the list form."""
    __slots__ = ('_t', '_d')
    __hash__ = None

    def __init__(self, pairs=()):
        self._t = array('d')
        self._d = array('q')
        for t, d in pairs:
            self._t.append(t)
            self._d.append(d)

    def __len__(self):
        return len(self._t)

    def __iter__(self):
        for t, d in zip(self._t, self._d):
            yield [t, d]

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [[t, d] for t, d in zip(self._t[index], self._d[index])]
        return [self._t[index], self._d[index]]

    def __eq__(self, other):
        try:
            return list(self) == [list(pair) for pair in other]
        except TypeError:
            return NotImplemented

    def __repr__(self):
        return repr(list(self))


def compact_series(series: List[List[float]]):
    """*series* as a Series, or as it is when a damage is not an int."""
    try:
        return Series(series)
    except TypeError:
        return series


def per_second(series: List[List[float]], duration_s: float) -> List[int]:
    """The series as damage per whole second of the fight: index k holds
    the damage of the bucket nearest second k, for k = 0 .. ceil(duration);
    a bucket before the fight's start counts in its first second."""
    seconds = max(int(duration_s + 0.999999), 1)
    values = [0] * (seconds + 1)
    for t, damage in series:
        k = min(max(int(round(t)), 0), seconds)
        values[k] += int(damage)
    return values


def smoothed_dps(series: List[List[float]], window_s: int,
                 duration_s: float) -> List[Tuple[float, float]]:
    """Combat Metrics' smoothed curve: (x, dps) points, each the mean damage
    per second over a centred window of *window_s* seconds, from the
    fight's start to its end, the first and last values carried to the
    edges. Empty for a fight without damage."""
    if not series or duration_s <= 0:
        return []
    values = per_second(series, duration_s)
    window = max(1, min(int(window_s), len(values)))
    last_start = len(values) - window
    points: List[Tuple[float, float]] = []
    running = sum(values[:window])
    for start in range(last_start + 1):
        if start:
            running += values[start + window - 1] - values[start - 1]
        points.append((start + window / 2.0, running / window))
    first_y, last_y = points[0][1], points[-1][1]
    return [(0.0, first_y)] + points + [(float(duration_s), last_y)]


def running_dps(series: List[List[float]], first_s: Optional[float],
                last_s: Optional[float], duration_s: float) -> List[Tuple[float, float]]:
    """Combat Metrics' total curve, the live figure as it stood: at each
    second from a second after the first hit to the end, the damage so far
    over the dps time so far (first hit to this second, or to the last hit
    once past it; a second at least), so the last point is the fight's dps.
    Empty for a fight without damage."""
    if not series or duration_s <= 0 or first_s is None or last_s is None:
        return []
    values = per_second(series, duration_s)
    points: List[Tuple[float, float]] = []
    total = 0
    for second, damage in enumerate(values):
        total += damage
        elapsed = min(float(last_s), float(second)) - float(first_s)
        if second < first_s + 1 or total <= 0:
            continue
        points.append((float(second), total / max(elapsed, MIN_DPS_TIME_S)))
    return points


class Window:
    """First and last log time of a run of hits (LibCombat's dpsstart and
    dpsend). Times are the log's milliseconds; the log is ordered, min and
    max keep it honest should it not be."""
    __slots__ = ('first_ms', 'last_ms')

    def __init__(self):
        self.first_ms: Optional[int] = None
        self.last_ms: Optional[int] = None

    def note(self, ts: int) -> None:
        if self.first_ms is None or ts < self.first_ms:
            self.first_ms = ts
        if self.last_ms is None or ts > self.last_ms:
            self.last_ms = ts

    @property
    def span_ms(self) -> int:
        if self.first_ms is None:
            return 0
        return self.last_ms - self.first_ms

    def as_dict(self, origin_ms: Optional[int] = None) -> dict:
        """The span as primitives; with *origin_ms* (the fight's start) also
        the first and last hit as seconds into the fight."""
        out = {'first_ms': self.first_ms, 'last_ms': self.last_ms, 'span_ms': self.span_ms}
        if origin_ms is not None and self.first_ms is not None:
            out['first_s'] = (self.first_ms - origin_ms) / 1000.0
            out['last_s'] = (self.last_ms - origin_ms) / 1000.0
        return out


class AbilityDamage:
    """One row of a breakdown: an ability, cast by the player or by a pet of
    theirs, and what its hits did."""
    __slots__ = ('ability_id', 'pet', 'damage', 'hits', 'crits', 'blocked',
                 'shielded', 'ticks', 'max_hit', 'min_hit', 'tick_damage', 'area_damage',
                 'types')

    def __init__(self, ability_id: str, pet: bool):
        self.ability_id = ability_id
        self.pet = pet
        self.damage = 0  # every counted result, the absorbs included
        self.hits = 0  # hits that landed: normal, critical, blocked
        self.crits = 0
        self.blocked = 0
        self.shielded = 0  # damage a shield absorbed (DAMAGE_SHIELDED lines)
        self.ticks = 0  # of the hits, damage-over-time ticks
        self.max_hit = 0
        self.min_hit = 0
        # The kinds of the hits (damage_kinds): the damage the ticks did,
        # the damage from area hits, and the damage per type label
        self.tick_damage = 0
        self.area_damage = 0
        self.types: Counter = Counter()

    def note(self, hit: int, result: str, damage_type: str = '', area: bool = False) -> None:
        self.damage += hit
        if result == SHIELDED:
            self.shielded += hit
            return
        self.hits += 1
        if result in CRIT_RESULTS:
            self.crits += 1
        if result == BLOCKED:
            self.blocked += 1
        if result in TICK_RESULTS:
            self.ticks += 1
            self.tick_damage += hit
        if area:
            self.area_damage += hit
        self.types[classify(result, damage_type)['type']] += hit
        if hit > self.max_hit:
            self.max_hit = hit
        if self.min_hit == 0 or hit < self.min_hit:
            self.min_hit = hit

    def move_to_area(self, hit: int) -> None:
        """A cast counted single struck a second unit: its hit was area."""
        self.area_damage += hit

    def as_dict(self, name: str, icon: str) -> dict:
        return {'id': self.ability_id, 'name': name, 'icon': icon, 'pet': self.pet,
                'damage': self.damage, 'hits': self.hits, 'crits': self.crits,
                'blocked': self.blocked, 'shielded': self.shielded, 'ticks': self.ticks,
                'max': self.max_hit, 'min': self.min_hit, 'tick_damage': self.tick_damage,
                'area_damage': self.area_damage, 'types': dict(self.types)}


class TargetDamage:
    """A player's damage to one unit, with the span of their hits on it."""
    __slots__ = ('unit_id', 'boss', 'damage', 'hits', 'window')

    def __init__(self, unit_id: str, boss: bool):
        self.unit_id = unit_id
        self.boss = boss
        self.damage = 0
        self.hits = 0
        self.window = Window()

    def note(self, ts: int, hit: int, result: str) -> None:
        self.damage += hit
        if result != SHIELDED:
            self.hits += 1
        self.window.note(ts)

    def as_dict(self, name: str) -> dict:
        row = {'unit_id': self.unit_id, 'name': name, 'boss': self.boss,
               'damage': self.damage, 'hits': self.hits}
        row.update(self.window.as_dict())
        return row


class PlayerDamage:
    """One player's damage in a fight: totals, the spans their dps divides
    by, and the breakdowns the damage window shows."""
    __slots__ = ('damage', 'boss_damage', 'window', 'boss_window',
                 'abilities', 'boss_abilities', 'targets', 'buckets', 'boss_buckets',
                 'target_buckets', 'kinds', '_pending')

    def __init__(self):
        self.damage = 0
        self.boss_damage = 0
        self.window = Window()
        self.boss_window = Window()
        self.abilities: Dict[Tuple[str, bool], AbilityDamage] = {}
        self.boss_abilities: Dict[Tuple[str, bool], AbilityDamage] = {}
        self.targets: Dict[str, TargetDamage] = {}
        # Damage per log second, for the graph (see series_of)
        self.buckets: Dict[int, int] = {}
        self.boss_buckets: Dict[int, int] = {}
        # And per target unit, for the penetration and crit figures
        # (pen_crit weighs the debuffs on each target by the damage dealt
        # to it that second)
        self.target_buckets: Dict[str, Dict[int, int]] = {}
        # The kinds of the damage (damage_kinds): the sides of the three
        # splits, the damage per type label, what rule classed the area
        # side, and the shield absorbs, which sit outside the splits
        self.kinds: Dict[str, object] = {
            'direct': 0, 'dot': 0, 'area': 0, 'single': 0, 'martial': 0, 'magical': 0,
            'oblivion': 0, 'other': 0, 'shielded': 0, 'types': Counter(), 'rules': Counter()}
        # cast key -> [(rows, hit)] counted single until the cast hits a second
        # target and the watcher moves them to area
        self._pending: Dict[tuple, List[Tuple[tuple, int]]] = {}

    def note(self, ts: int, hit: int, result: str, ability_id: str, pet: bool,
             target_id: str, boss: bool, damage_type: str = '', area=None,
             cast_key=None, watch=None) -> None:
        """One hit. *damage_type* is the line's; *area* is (area?, rule)
        from damage_kinds.area_of, None when nothing classes it; *watch*
        registers a callback for the cast's second target (CastIndex.watch)
        so a hit counted single is moved to area when the cast turns out to
        be one, *cast_key* naming the cast."""
        self.damage += hit
        self.window.note(ts)
        _bucket(self.buckets, ts, hit)
        _bucket(self.target_buckets.setdefault(target_id, {}), ts, hit)
        if boss:
            _bucket(self.boss_buckets, ts, hit)
        is_area, rule = area if area else (False, 'none')
        key = (ability_id, pet)
        row = self.abilities.get(key)
        if row is None:
            row = self.abilities[key] = AbilityDamage(ability_id, pet)
        row.note(hit, result, damage_type, is_area)
        rows = (row,)
        target = self.targets.get(target_id)
        if target is None:
            target = self.targets[target_id] = TargetDamage(target_id, boss)
        target.note(ts, hit, result)
        if boss:
            self.boss_damage += hit
            self.boss_window.note(ts)
            row = self.boss_abilities.get(key)
            if row is None:
                row = self.boss_abilities[key] = AbilityDamage(ability_id, pet)
            row.note(hit, result, damage_type, is_area)
            rows = rows + (row,)
        kinds = self.kinds
        if result == SHIELDED:
            kinds['shielded'] += hit
            return
        classed = classify(result, damage_type)
        if classed['time'] in ('direct', 'dot'):
            kinds[classed['time']] += hit
        kinds[classed['school']] += hit
        kinds['types'][classed['type']] += hit
        kinds['rules'][rule] += hit
        if is_area:
            kinds['area'] += hit
        else:
            kinds['single'] += hit
            if watch is not None and rule == 'none' and cast_key is not None:
                pending = self._pending.get(cast_key)
                if pending is None:
                    pending = self._pending[cast_key] = []
                    watch(lambda key=cast_key: self._cast_became_area(key))
                pending.append((rows, hit))

    def _cast_became_area(self, cast_key) -> None:
        """The cast hit a second target: its earlier hits were area."""
        kinds = self.kinds
        for rows, hit in self._pending.pop(cast_key, ()):
            kinds['single'] -= hit
            kinds['area'] += hit
            kinds['rules']['none'] -= hit
            kinds['rules']['cast'] += hit
            for row in rows:
                row.move_to_area(hit)

    def kinds_snapshot(self) -> dict:
        """The kinds as primitives for the build window: the sides, the
        types, the rules and the shield absorbs, with 'total' the damage
        the sides sum (every hit but the absorbs)."""
        kinds = self.kinds
        out = {key: kinds[key] for key in ('direct', 'dot', 'area', 'single', 'martial',
                                           'magical', 'oblivion', 'other', 'shielded')}
        out['total'] = self.damage - kinds['shielded']
        out['types'] = dict(kinds['types'])
        out['rules'] = dict(kinds['rules'])
        return out

    def dps(self) -> float:
        return dps(self.damage, self.window.span_ms)

    def boss_dps(self) -> float:
        return dps(self.boss_damage, self.boss_window.span_ms)

    def snapshot(self, name_of: Callable[[str], str], icon_of: Callable[[str], str],
                 unit_name_of: Callable[[str], str], origin_ms: Optional[int] = None) -> dict:
        """Plain dicts and lists for a fight entry (the GUI reads it on its
        own thread): totals, both windows (with the hits' offsets into the
        fight when *origin_ms* is its start), the ability rows for all
        targets and for the bosses, largest damage first, the targets, and
        the damage per second of the fight for the graph (series_of)."""
        def rows(table: Dict[Tuple[str, bool], AbilityDamage]) -> List[dict]:
            out = [row.as_dict(name_of(row.ability_id), icon_of(row.ability_id))
                   for row in table.values()]
            out.sort(key=lambda r: (-r['damage'], r['name']))
            return out
        targets = [t.as_dict(unit_name_of(t.unit_id)) for t in self.targets.values()]
        targets.sort(key=lambda r: (-r['damage'], r['name']))
        return {
            'total': self.damage, 'boss': self.boss_damage,
            'window': self.window.as_dict(origin_ms),
            'boss_window': self.boss_window.as_dict(origin_ms),
            'abilities': rows(self.abilities), 'boss_abilities': rows(self.boss_abilities),
            'targets': targets,
            'series': compact_series(series_of(self.buckets, origin_ms)),
            'boss_series': compact_series(series_of(self.boss_buckets, origin_ms)),
            # The kinds of the damage, for the build window (damage_kinds)
            'kinds': self.kinds_snapshot(),
        }


class FightDamage:
    """The fight's damage: the group's spans and each player's record. The
    totals live on the encounter (total_damage, boss_damage); this adds
    the time they happened over, the breakdowns, and the group's damage
    per second for the graph."""
    __slots__ = ('window', 'boss_window', 'players', 'buckets', 'boss_buckets',
                 'target_buckets')

    def __init__(self):
        self.window = Window()
        self.boss_window = Window()
        self.players: Dict[str, PlayerDamage] = {}
        self.buckets: Dict[int, int] = {}
        self.boss_buckets: Dict[int, int] = {}
        # The group's damage per log second per target unit (pen_crit)
        self.target_buckets: Dict[str, Dict[int, int]] = {}

    def note(self, player_id: str, ts: int, hit: int, result: str, ability_id: str,
             pet: bool, target_id: str, boss: bool, damage_type: str = '', area=None,
             cast_key=None, watch=None, also: str | None = None) -> None:
        """One hit: once for the group, then on *player_id*'s record and, when
        *also* names another record, on that one too as a pet's hit (a
        companion's hit counted as its owner's as well, see companions.py).
        *damage_type*, *area*, *cast_key* and *watch* are the kinds of the
        damage (damage_kinds), handed to each record; the cast watcher takes
        a callback per record."""
        self.window.note(ts)
        _bucket(self.buckets, ts, hit)
        _bucket(self.target_buckets.setdefault(target_id, {}), ts, hit)
        if boss:
            self.boss_window.note(ts)
            _bucket(self.boss_buckets, ts, hit)
        for record_id, as_pet in ((player_id, pet), (also, True)):
            if record_id is None:
                continue
            player = self.players.get(record_id)
            if player is None:
                player = self.players[record_id] = PlayerDamage()
            player.note(ts, hit, result, ability_id, as_pet, target_id, boss,
                        damage_type, area, cast_key, watch)

    def player(self, player_id: str) -> PlayerDamage:
        """The player's record, an empty one for a player who dealt nothing."""
        return self.players.get(player_id) or PlayerDamage()

    def series(self, origin_ms: Optional[int] = None) -> dict:
        """The group's damage per second for a fight entry, for the graph:
        the series for all targets and for the bosses, and the spans the
        running figures start and end at (see series_of, Window.as_dict)."""
        return {
            'all': compact_series(series_of(self.buckets, origin_ms)),
            'boss': compact_series(series_of(self.boss_buckets, origin_ms)),
            'window': self.window.as_dict(origin_ms),
            'boss_window': self.boss_window.as_dict(origin_ms),
        }
