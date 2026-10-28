"""
Magicka, stamina and ultimate spent and gained in a fight (engine side, no
Qt). Issue #125.

Design: every unit state in the log is ``unitId, health, magicka, stamina,
ultimate, werewolf, shield, x, y, heading`` with each pool as
``current/max``, and every group member's pools are real values, not only
the logging player's (each of 12 players in an Aetherian Archive split of
2026-10-24 had 1,100 to 2,600 distinct states, sampled in combat at a p95
gap of about 100 ms). Nothing logs a cost: a skill's cost is a drop in the
caster's state, nearly always already in the state its BEGIN_CAST line
carries (Stampede -3,443 stamina 141 of 141 times), and sometimes on a line
written at the same millisecond just before it. So the figures are read
from the states:

- Spent is the sum of the drops between a player's consecutive states, and
  a drop at the millisecond of one of the player's casts is that cast's
  cost; light and heavy attacks and weapon swaps cost nothing and are never
  charged. Over the AA and Sunspire splits that put 70 to 91% of magicka
  and 60 to 78% of stamina spending on casts; the rest (blocking,
  sprinting, a cost written later, like Killer's Blade's on the next line)
  leaves no line of its own and is shown as other spending, not guessed.
- A gain the game logs is a COMBAT_EVENT POWER_ENERGIZE, whose powerType
  is a flag (1 magicka, 2 werewolf, 4 stamina, 8 ultimate) and whose unit
  state is the one after the gain (8,455 of 9,262 rows moved the pool by
  the logged amount). Its ``overflow`` is always 0, so the gain booked to
  the row's ability is the pool's own rise there, and a row arriving at a
  full pool is waste (logged amount less the rise). The giver is the row's
  source when that is another player (Pillager's Profit, Bountiful
  Harvest); a source that is not a player, like the enemy carrying Minor
  Magickasteal, names nobody.
- Every other rise is "regeneration and unlogged": base regeneration, base
  ultimate generation and ultimate on hit have no line (only 38 to 55% of
  magicka and stamina rises, and a quarter of ultimate rises, were on an
  energize row). It is a residual, not a measurement of regeneration.
- Logged ultimate never arrived at a full pool (0 of 5,728 points), so lost
  ultimate cannot be counted; the time at full ultimate is the figure (0 to
  46% of combat across the AA group). A state's current can exceed its max
  (19,062 magicka states in AA: the max lags), so "full" is current >= max.

The figures are net per observation: a cost and a gain inside one gap
cancel. On trial logs that is a few percent; reading the effect lines'
source states too, as the engine does, keeps it there (a solo March of
Sacrifices split read stamina spent 29k without them, 41k with).

The engine can resume a fight the game cut in two (COMBAT_RESUME_MS), so
the figures are kept in one-second buckets per player and summed over the
fight's window, then pruned at fight end as casts.py prunes its casts. A
step between two states is capped at MAX_STEP_MS for the time at full, so
the first state of a fight does not carry the idle time before it.
"""

from collections import defaultdict
from collections.abc import Callable

import casts

POOLS = ("magicka", "stamina", "ultimate")
# COMBAT_EVENT powerType -> pool index (werewolf, 2, is not counted)
POWER_TYPES = {"1": 0, "4": 1, "8": 2}
ENERGIZE = "POWER_ENERGIZE"
# Casts that cost nothing: a drop at their millisecond is not theirs
FREE_CASTS = casts.LIGHT_ATTACKS | casts.HEAVY_ATTACKS | casts.SWAPS
# A channel whose cost comes with each tick and no cast line: the tick's
# damage id -> the skill (Pragmatic Fatecarver, -289 stamina with each of
# its hits in the Sunspire split of 2026-10-21; casts.CHANNEL_EFFECTS makes
# the cast). Exhausting Fatecarver's tick id was in no log surveyed
CHANNEL_TICKS = {"186370": "186366"}
MAX_STEP_MS = 2000
TOP = 5  # rows per pool in the spent on and gained from lists


class _Bucket:
    """One player's figures over one second."""

    __slots__ = ("cast_spend", "full_ms", "gained", "gains", "seen_ms", "spent", "wasted")

    def __init__(self):
        self.spent = [0, 0, 0]
        self.gained = [0, 0, 0]
        self.wasted = [0, 0, 0]
        self.full_ms = 0
        self.seen_ms = 0
        self.cast_spend: dict[tuple[int, str], list[int]] = {}  # (pool, ability) -> [total, casts]
        self.gains: dict[tuple[int, str, str], int] = {}  # (pool, ability, giver key) -> total


def _pools(mag: str, sta: str, ult: str):
    """((current x3), (max x3)) from three 'current/max' fields."""
    m_cur, m_max = mag.split("/")
    s_cur, s_max = sta.split("/")
    u_cur, u_max = ult.split("/")
    return ((int(m_cur), int(s_cur), int(u_cur)), (int(m_max), int(s_max), int(u_max)))


class ResourceRecorder:
    """Each player's resource figures over a BEGIN_LOG session, by second,
    until a fight's entry is built from them. Keyed by the player's record
    id in the encounter (CombatEncounter.player_of), as casts.py is."""

    def __init__(self):
        self._buckets: dict[str, dict[int, _Bucket]] = defaultdict(dict)
        # key -> [time, raw fields, current, max, ms seen and ms at full
        # ultimate not booked yet]
        self._last: dict[str, list] = {}
        # key -> [time, track id, ability, pools charged]: the cast at that ms
        self._cast: dict[str, list] = {}
        # key -> [time, [drop x3]]: drops at that ms not charged to a cast yet
        self._pending: dict[str, list] = {}

    def reset(self) -> None:
        """A new BEGIN_LOG session: timestamps restart."""
        self._buckets.clear()
        self._last.clear()
        self._cast.clear()
        self._pending.clear()

    def _bucket(self, key: str, timestamp: int) -> _Bucket:
        buckets = self._buckets[key]
        second = timestamp // 1000
        bucket = buckets.get(second)
        if bucket is None:
            bucket = buckets[second] = _Bucket()
        return bucket

    def _flush(self, key: str, last: list) -> None:
        """Book the time gathered since the last flush to its second."""
        if last[4]:
            bucket = self._bucket(key, last[0])
            bucket.seen_ms += last[4]
            bucket.full_ms += last[5]
            last[4] = last[5] = 0

    def _charge(self, key: str, bucket: _Bucket, cast: list, pool: int, amount: int) -> None:
        """Book *amount* of *pool* to the cast; a cast counts once per pool."""
        entry = bucket.cast_spend.get((pool, cast[2]))
        if entry is None:
            entry = bucket.cast_spend[(pool, cast[2])] = [0, 0]
        entry[0] += amount
        if pool not in cast[3]:
            cast[3].add(pool)
            entry[1] += 1

    def note_cast(self, key: str, timestamp: int, track_id: str, ability_id: str,
                  counted: bool = True) -> None:
        """A BEGIN_CAST by the player, before its state is observed. A second
        line under the same castTrackId is the same cast. *counted* False
        for a channel's tick (CHANNEL_TICKS): its cost is the skill's, but
        it is not another cast."""
        if ability_id in FREE_CASTS:
            return
        cast = self._cast.get(key)
        if cast is not None and cast[1] == track_id and (cast[0] == timestamp or not counted):
            # The same cast: a tick charges its millisecond to it, and the
            # first that costs anything counts it
            if cast[0] == timestamp:
                return
            cast[0] = timestamp
        else:
            cast = self._cast[key] = [timestamp, track_id, ability_id,
                                      set() if counted else {0, 1, 2}]
        # Drops written at this millisecond before the cast's own line
        pending = self._pending.pop(key, None)
        if pending is not None and pending[0] == timestamp:
            bucket = self._bucket(key, timestamp)
            for pool, amount in enumerate(pending[1]):
                if amount:
                    self._charge(key, bucket, cast, pool, amount)

    def observe(self, key: str, timestamp: int, mag: str, sta: str, ult: str,
                energize: tuple | None = None) -> None:
        """One of the player's unit states (its magicka, stamina and
        ultimate fields). *energize*: (pool, ability id, logged amount,
        giver key or '') when this is the pool owner's state on a
        POWER_ENERGIZE row."""
        last = self._last.get(key)
        raw = (mag, sta, ult)
        if last is None:
            try:
                current, maximum = _pools(mag, sta, ult)
            except ValueError:
                return
            self._last[key] = [timestamp, raw, current, maximum, 0, 0]
            return
        # The time since the last state, booked once a second (most states
        # repeat the last exactly)
        if timestamp // 1000 != last[0] // 1000:
            self._flush(key, last)
        step = min(max(0, timestamp - last[0]), MAX_STEP_MS)
        last[4] += step
        before, before_max = last[2], last[3]
        if before[2] >= before_max[2] > 0:
            last[5] += step
        last[0] = timestamp
        if raw == last[1] and energize is None:
            return
        if raw == last[1]:
            current, maximum = before, before_max
        else:
            try:
                current, maximum = _pools(mag, sta, ult)
            except ValueError:
                return
            last[1], last[2], last[3] = raw, current, maximum
        bucket = self._bucket(key, timestamp)
        if energize is not None:
            pool, ability_id, amount, giver = energize
            rise = max(0, current[pool] - before[pool])
            if rise:
                gain_key = (pool, ability_id, giver)
                bucket.gains[gain_key] = bucket.gains.get(gain_key, 0) + rise
            if before[pool] >= before_max[pool] > 0 and amount > rise:
                bucket.wasted[pool] += amount - rise
        if current is before:
            return
        cast = self._cast.get(key)
        at_cast = cast is not None and cast[0] == timestamp
        for pool in range(3):
            change = current[pool] - before[pool]
            if change > 0:
                bucket.gained[pool] += change
            elif change < 0:
                bucket.spent[pool] -= change
                if at_cast:
                    self._charge(key, bucket, cast, pool, -change)
                else:
                    pending = self._pending.get(key)
                    if pending is None or pending[0] != timestamp:
                        pending = self._pending[key] = [timestamp, [0, 0, 0]]
                    pending[1][pool] -= change

    def fight_summary(self, key: str, start: int, end: int, duration_s: float,
                      present_pct: float | None = None,
                      name_of: Callable[[str], str] | None = None,
                      giver_name: Callable[[str], str] | None = None) -> dict | None:
        """The fight entry's 'resources' for a player, or None when none of
        their states fell in the fight: per pool 'spent', 'gained', 'logged'
        (gains on energize rows), 'wasted', 'on_casts' (spent on casts) and
        'spent_ps' / 'gained_ps' over the fight's duration (or the share of
        it a player who left was there for); 'full_pct', the share of the
        time at full ultimate; 'spent_on' and 'gained_from', the top TOP of
        each pool with a 'more' row for the rest."""
        state = self._last.get(key)
        if state is not None:
            self._flush(key, state)
        buckets = self._buckets.get(key)
        if not buckets:
            return None
        first, last = start // 1000, end // 1000
        spent, gained, wasted = [0, 0, 0], [0, 0, 0], [0, 0, 0]
        full_ms = seen_ms = 0
        cast_spend: dict[tuple[int, str], list[int]] = {}
        gains: dict[tuple[int, str, str], int] = {}
        for second, bucket in buckets.items():
            if not first <= second <= last:
                continue
            for pool in range(3):
                spent[pool] += bucket.spent[pool]
                gained[pool] += bucket.gained[pool]
                wasted[pool] += bucket.wasted[pool]
            full_ms += bucket.full_ms
            seen_ms += bucket.seen_ms
            for spend_key, (total, count) in bucket.cast_spend.items():
                entry = cast_spend.setdefault(spend_key, [0, 0])
                entry[0] += total
                entry[1] += count
            for gain_key, total in bucket.gains.items():
                gains[gain_key] = gains.get(gain_key, 0) + total
        if not seen_ms:
            return None
        seconds = duration_s
        if present_pct is not None:
            seconds *= max(0.0, min(100.0, float(present_pct))) / 100.0
        name_of = name_of or (lambda ability_id: "")
        giver_name = giver_name or (lambda giver: giver)
        pools = []
        for pool in range(3):
            on_casts = sum(total for (p, _a), (total, _n) in cast_spend.items() if p == pool)
            logged = sum(total for (p, _a, _g), total in gains.items() if p == pool)
            pools.append({
                "spent": spent[pool], "gained": gained[pool], "logged": logged,
                "wasted": wasted[pool], "on_casts": min(on_casts, spent[pool]),
                "spent_ps": spent[pool] / seconds if seconds > 0 else 0.0,
                "gained_ps": gained[pool] / seconds if seconds > 0 else 0.0,
            })
        spent_on, gained_from = [], []
        for pool in range(3):
            rows = sorted(((total, count, ability_id)
                           for (p, ability_id), (total, count) in cast_spend.items() if p == pool),
                          reverse=True)
            for total, count, ability_id in rows[:TOP]:
                spent_on.append({"pool": pool, "id": ability_id, "name": name_of(ability_id) or ability_id,
                                 "casts": count, "total": total})
            rest = sum(row[0] for row in rows[TOP:])
            if rest:
                spent_on.append({"pool": pool, "more": len(rows) - TOP, "total": rest})
            rows = sorted(((total, ability_id, giver)
                           for (p, ability_id, giver), total in gains.items() if p == pool),
                          reverse=True)
            for total, ability_id, giver in rows[:TOP]:
                gained_from.append({"pool": pool, "id": ability_id,
                                    "name": name_of(ability_id) or ability_id,
                                    "giver": giver_name(giver) if giver else "", "total": total})
            rest = sum(row[0] for row in rows[TOP:])
            if rest:
                gained_from.append({"pool": pool, "more": len(rows) - TOP, "total": rest})
        return {"pools": pools, "full_pct": 100.0 * full_ms / seen_ms,
                "spent_on": spent_on, "gained_from": gained_from}

    def prune_before(self, timestamp: int) -> None:
        """Forget the seconds before *timestamp*'s."""
        second = timestamp // 1000
        for key in list(self._buckets):
            kept = {s: b for s, b in self._buckets[key].items() if s >= second}
            if kept:
                self._buckets[key] = kept
            else:
                del self._buckets[key]


def energize_of(fields: list) -> tuple | None:
    """(pool, ability id, logged amount) of a COMBAT_EVENT entry's fields
    when it is a magicka, stamina or ultimate POWER_ENERGIZE, else None.
    Fields after the time and event type: [0] actionResult, [2] powerType,
    [3] hitValue, [6] abilityId."""
    if fields[0] != ENERGIZE:
        return None
    pool = POWER_TYPES.get(fields[2])
    if pool is None:
        return None
    try:
        return pool, fields[6], int(fields[3])
    except ValueError:
        return None
