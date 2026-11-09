"""
The group's hits between fights, waiting for the next fight's line (engine
side, no Qt). Issue #162, part 1.

Design: The hits before the line. A fight runs from the logging player's
BEGIN_COMBAT to their END_COMBAT, and the group's first hits often land
before the line (see fight_opener). Before this rule such a hit fell on the
encounter END_COMBAT had closed and published, which nothing builds again
unless the fight carries on (the engine's COMBAT_RESUME_MS), and
BEGIN_COMBAT opened a new encounter without it: it was counted in no
fight. Two fights had them, a zone's first, whose encounter is the zone's
own and takes every hit from the zone's start, and a fight the game cut in
two, which reopens its encounter with the hits between the two lines.
Replayed through 0.38.0 and through this rule, 395 split logs (8,765
fights, January to October 2026) count such hits in 3,831 fights (43.7%),
a median 0.04% of the fight's damage (p90 1.3%): the group's dps time
grows by a median 0.5 s (p90 1.5 s) and its dps falls by a median 1.1%
(p10 9.1%, beyond 5% in 915 fights), since the time grows more than the
damage; 4,399 player rows move, a median 2.2% either way (p90 12.9%), the
logging player's in 686 fights, and 22 rows had damage only before the
line. Combat Metrics counts the logging player's direct hits before the
line too.

At the line the engine cannot know which enemies the fight will hit. It
counts every hit from the opener's moments, the last OPENER_WINDOW_MS,
unless the fight that ended had hit the same enemy (those hits are the
group fighting on, issue #162's part 2) or the enemy died or left before
the line (fight_opener.gone_before, as the opener drops it, so the line and
the figures agree). A DoT tick counts like every other damage result. The
hits keep their own times: the dps time, the damage window ("first hit 0.4
s before the pull"), boss dps, the kinds, the breakdowns, the penetration
figures' weighting and every row take them, and a player whose only damage
came before the line has a row's dps; the fight's clock (duration_s) stays
BEGIN_COMBAT to END_COMBAT. The DPS graph puts a second before the fight's
start in its second 0 (damage_stats.per_second), and its running figure
runs from the first hit, so it ends on the fight's dps. A fight that takes
hits has met an enemy, and is listed. An enemy hit only before the line is
one of the fight's, as in a zone's first fight: in the replay the name
shown (the most damaged enemy) changed in 37 fights, 32 of them without a
boss, a pull's bosses in 20 (3 fights gained a pull, all "Left"), the
uptime line's per-enemy items in 23, and a tank's damage-share finding on
12 rows; no fight was added, lost or published at another time. Fight by
fight, the replay took what a survey of the hits between fights predicts:
in 3,758 fights the hits on the new fight's enemies exactly, in 83 those
and the hits on enemies of neither fight still alive at the line, and in
13 the hits on a new pack after a combat that met no enemy, which the
survey did not follow; the other 12 are blips and the fights after them
(80.6 M in all, 0.06% of the damage).

Blips. A fight shorter than the engine's BLIP_MS (1 s) from BEGIN_COMBAT
to END_COMBAT is a blip: the game puts the logging player in combat for
some milliseconds, often as a boss appears (Volenfell's Guardian, four
times in four seconds; Halls of Fabrication's Committee), and the fight is
listed when it met an enemy. A blip takes none of the hits from before its
line. They wait for the next line, where only its last OPENER_WINDOW_MS
count, and the ended fight is still the last one that took hits, whose
enemies they leave out: a blip's own few hits are no reason to leave one
out. Of 48 blips in the 29 logs with one listed, 19 had hits of their own,
on some of the next fight's enemies in 5 and of the fight before's in 4,
never on the fight before's alone. Taking the hits, 30 of the 46 listed
blips had damage they did not deal, 17 a boss's, 18 read as a pull of a
boss the group left ("Left"), and the fight after a blip lost its first
hits; now none does, the 18 blips with damage of their own keeping it.
The next line takes back little of their 3.0 M: most of it came more than
10 s before the next fight (a Dreadsail Keelcutter's 649 k, 28 s before),
and counts in no fight, as before.

A combat with no enemy in it (held back, the engine's _note_enemy_met) is
no fight either: it takes no hits and leaves the waiting ones as they
are, the last listed fight still the ended one, so the group finishing
that fight's enemies after a broken Brimstone Orb is not the next fight's
opening. Should it be listed after all, it settles then, as any fight.
In the replay no such hit came up: the 13 fights that open after a combat
with no enemy took hits on new enemies only (in Sanity's Edge the next
pack's Wamasus, units 602 to 626, where the fight before had fought unit
333).

Where the hits wait: here, one ledger for the analyzer (WaitingHits), told
of each fight boundary as the opener's memory is. Each hit after
END_COMBAT still goes on the closed encounter as it comes, since a fight
the game cut in two reopens that encounter with them, its cast watchers
and all; the ledger keeps a copy, at most the last 10 s, read as the
closed encounter read it (the kinds once, for both): the engine's record
of its enemy, so a unit id handed out again is not the ended fight's
enemy; whose it is (CombatEncounter.hitter_of), so a player back on a new
unit id, re-keyed at the line, keeps their hits and a pet removed before
the line (a Blastbones blows up and goes) is its owner's; and its kinds.
The line takes the copies, the hitters still on the new fight's list, and
puts their casts back in the kinds index it has just emptied, so a cast
that strikes another unit after the line is area on both sides (in the
replay 1.0 M of 75 G moved from single to area, in 59 fights, and 7.9 M of
area damage was read by its cast rather than by the ability's session).
END_COMBAT counts them by the same code as any hit, before the entry is
built, once the fight's length shows it is no blip: nothing reads a
fight's damage before then. Then the waiting starts again, and the ended
fight's enemies are the records it hit. A fight carried on keeps the
copies dealt before its END_COMBAT (a blip's, waiting on) and drops the
later ones, which are on its encounter; a held combat listed late does the
same, its entry having the later ones.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, NamedTuple

import fight_opener

if TYPE_CHECKING:
    from esolog_tail import EnemyInfo, PlayerInfo


class GroupHit(NamedTuple):
    """One hit of the group's on a hostile, as the engine counted it on the
    closed encounter (ESOLogAnalyzer._credit_enemy_hit), kept for the next
    fight's line."""
    timestamp: int
    result: str
    value: int
    source_id: str
    target_id: str
    enemy: EnemyInfo  # the engine's record of the target as it was hit
    ability_id: str
    damage_type: str
    cast_id: str
    # The kinds' (area?, rule) as the cast index read the hit (damage_kinds)
    area: tuple[bool, str]
    # Whose the hit is, (player, companion row key or None, a pet's?), as the
    # closed encounter credited it (CombatEncounter.add_damage_to_player)
    hitter: tuple[PlayerInfo | None, str | None, bool]


class WaitingHits:
    """The group's hits since the last fight that took hits ended, the last
    OPENER_WINDOW_MS of them, and the enemies that fight hit: what a
    fight's line takes (see the module notes). The engine owns one and
    tells it each fight boundary; a combat held for want of an enemy, or a
    blip, is none."""

    def __init__(self):
        self._hits: deque[GroupHit] = deque()
        self._ended: frozenset = frozenset()  # EnemyInfo records, by identity

    def keep(self, hit: GroupHit) -> None:
        """A hit dealt after END_COMBAT, counted on the closed encounter."""
        hits = self._hits
        hits.append(hit)
        horizon = hit.timestamp - fight_opener.OPENER_WINDOW_MS
        while hits[0].timestamp < horizon:
            hits.popleft()

    def take(self, start_ms: int, targets_of: Callable[[str, str], int]) -> list[GroupHit]:
        """The hits the fight whose BEGIN_COMBAT is at *start_ms* takes:
        from the last OPENER_WINDOW_MS, not on an enemy the ended fight hit,
        nor on one that died or left before the line. *targets_of* is the
        kinds index's (damage_kinds.CastIndex.targets_of), read before the
        line empties it: a hit read single whose cast struck a second unit
        since is area, on the waiting copy too. The hits wait on: the
        fight's END_COMBAT tells whether it took them (settled)."""
        horizon = start_ms - fight_opener.OPENER_WINDOW_MS
        ended = self._ended
        waiting: deque[GroupHit] = deque()
        taken = []
        for hit in self._hits:
            if hit.area == (False, "none") and targets_of(hit.source_id, hit.cast_id) >= 2:
                hit = hit._replace(area=(True, "cast"))
            waiting.append(hit)
            if not (hit.timestamp < horizon or hit.enemy in ended
                    or fight_opener.gone_before(hit.enemy, start_ms)):
                taken.append(hit)
        self._hits = waiting
        return taken

    def settled(self, hit_enemies: Iterable[EnemyInfo]) -> None:
        """A listed fight of BLIP_MS or more ended and took its hits: the
        waiting starts again, and a later line leaves the enemies it hit
        (*hit_enemies*, the records) to it."""
        self._hits.clear()
        self._ended = frozenset(hit_enemies)

    def carried_on(self, ended_ms: int) -> None:
        """The fight that ended at *ended_ms* carries on (the engine's
        COMBAT_RESUME_MS): the hits since are on its encounter. The earlier
        ones, a blip's, wait on, and the ended fight stays."""
        self._drop_since(ended_ms)

    def listed_late(self, ended_ms: int) -> None:
        """A combat held for want of an enemy, ended at *ended_ms*, is
        listed after all: its entry is built from its encounter, which has
        the hits since."""
        self._drop_since(ended_ms)

    def reset(self) -> None:
        """A zone change or a new log session: unit ids start over."""
        self._hits.clear()
        self._ended = frozenset()

    def _drop_since(self, ended_ms: int) -> None:
        self._hits = deque(hit for hit in self._hits if hit.timestamp < ended_ms)
