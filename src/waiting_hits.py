"""
The group's hits between fights: waiting for the next fight's line, or the
group fighting on after the fight that ended (engine side, no Qt). Issue
#162, parts 1 and 2.

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

The group fighting on (part 2). END_COMBAT is the logging player's line as
well: when they die, or step out of combat while the rest of the group
fights on, the group's hits after it went on the closed encounter, which
nothing built again, and counted in no fight. In the survey's 395 split
logs, 235 fights had such hits on their own enemies before the next line,
119.5 M of damage: a fifth or more of the fight's in 25, and in a Hel Ra
Citadel boss fight 16.4 M of its 48.2 M, the group fighting on for 64.7 s
and three of them dying as they did. From a listed fight's END_COMBAT (a
blip settles nothing, so none of its), a hit of the group's on an enemy
record the fight hit is the group fighting on while it comes within
FIGHT_ON_MS of END_COMBAT or of the last such hit: the fight's encounter
counts it as a hit in it, at its own time, DoT ticks too. The 3 s are the
survey's knee: a pause between two such hits was under 0.7 s in 99% of
them, and 3 s takes 99.4% of their damage where 15 s would add 0.3%.

Once the group has stopped, at the first log line past the wait (read at
the line's own time, which the parser does not give every event), at the
next fight's line, at a zone change or a new session, or at the log's end
(ESOLogAnalyzer.finish, which a replay calls), the fight is built again,
and the entry frontends hold takes what those hits decide
(take_damage_figures): the dps and its time, the graph's series, each
row's damage figures and the rows' order, the name shown (its most
damaged enemy), the penetration figures and the pull, read again against
the pull before it and with the boss as the group left it. The rest stays
as END_COMBAT left it, though the encounter has gone on gathering: the
deaths after LATE_DEATH_GRACE_MS, healing, damage taken, a player who came
after, the build findings (a tank's share of the damage among them), the
recaps, and the fight's time, which is the log's (the maintainer's
decision 6). That build has no side effect (the builder's *again*): a
tracker pruned then would forget the casts under way, and in a replay the
next fight counted a cast written over its line twice, in 12 rows.

Replayed through 0.39.0 and through this rule (411 split logs, 9,309
fights), 186 fights take hits fought on without being carried on: 80.6 M,
a median 0.81% of the fight's damage (p90 13.0%, over a fifth in 18).
Their group dps moves a median +0.12%, lower in 61 and higher in 124,
since a long mop-up after a kill lowers it: in a Hel Ra Citadel Yokeda
Rok'dun kill the group fought the adds on for 104 s after the 118 s fight,
and its dps reads 321k, not 500k, the boss dps unchanged, since it divides
by the hits on the bosses. No pull's verdict changes in them, and nothing
but the damage figures moves.

A boss fight carried on (decision 5's b). Combat beginning again later
than COMBAT_RESUME_MS after END_COMBAT carries the fight on, however long
after, when the fight had boss damage, the group has fought on since
without a pause of FIGHT_ON_MS, and an enemy it was hitting as the fight
ended (the engine's _engaged_at_end, the same record, alive) took one of
its hits since END_COMBAT within FIGHT_ON_MS of the line: one fight from
its first line to its last, the deaths, healing and other hits between
the lines its own, as a fight the game cut in two. Without the boss rule
the replay carried 51 fights on, trash among them: in four Hel Ra Citadel
runs the gargoyles the group was still finishing headed the Yokeda kill
(a 107 s kill read as a 205 s fight), and the maintainer chose boss pulls
only (2026-11-11). With it, 39 fights are 15 boss pulls again, 8 of them
Lord Falgravn's in Kyne's Aegis, which the logging player's deaths had cut
into as many as six parts (Lieutenant Njordal, added friendly, fights on
its floors), the others the Yokeda twins, Ansuul, Z'Maja and an overland
Dread Harvester; their pulls, Left or Lost sight on each cut part, now
read 10 kills and 5 wipes.

Where the hits wait: here, one ledger for the analyzer (WaitingHits), told
of each fight boundary as the opener's memory is. After a listed fight's
END_COMBAT a hit that is not the group fighting on waits here alone, never
on the closed encounter, whose entry is built again with the hits fought
on: read as that encounter would have credited it (CombatEncounter.
read_hit, the kinds once): the engine's record of its enemy, so a unit id
handed out again is not the ended fight's enemy; whose it is
(CombatEncounter.hitter_of), so a player back on a new unit id, re-keyed
at the line, keeps their hits and a pet removed before the line (a
Blastbones blows up and goes) is its owner's; and its kinds. The ledger
keeps the last 10 s of them, and every one since END_COMBAT while the
group may still fight on: a fight carried on takes those back
(carried_on) and counts them by the same code as any hit, its earlier
copies (a blip's) waiting on. The line takes the copies, the hitters
still on the new fight's list, and puts their casts back in the kinds
index it has just emptied, so a cast that strikes another unit after the
line is area on both sides (in the part 1 replay 1.0 M of 75 G moved from
single to area, in 59 fights, and 7.9 M of area damage was read by its
cast rather than by the ability's session). END_COMBAT counts them by the
same code as any hit, before the entry is built, once the fight's length
shows it is no blip: nothing reads a fight's damage before then. Then the
waiting starts again, the ended fight's enemies are the records it hit,
and the group may fight on them. A combat held for want of an enemy has
no entry: its encounter takes each hit as it comes and a copy waits, and
listed late it drops the copies since its END_COMBAT, its entry having
them.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, NamedTuple

import fight_opener

if TYPE_CHECKING:
    from esolog_tail import EnemyInfo, PlayerInfo
    from fight_history import FightHistoryEntry

# The group has stopped fighting on once this long passed without a hit on
# the ended fight's enemies (see the module notes)
FIGHT_ON_MS = 3000
# What the group fighting on changes in a fight's entry: the slots its
# damage decides, and the keys of each row's (see the module notes)
FOUGHT_ON_SLOTS = ('group_dps', 'group_boss_dps', 'dps_time_s', 'boss_dps_time_s',
                   'damage_series', 'boss_name', 'pen_crit', 'pull')
ROW_DAMAGE_KEYS = ('dps', 'boss_dps', 'dmg_pct', 'boss_pct', 'damage', 'pen_crit')


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
    blip, is none. From that fight's END_COMBAT it also tells the group
    fighting on its enemies (issue #162, part 2) until it stops."""

    def __init__(self):
        self._hits: deque[GroupHit] = deque()
        self._ended: frozenset = frozenset()  # EnemyInfo records, by identity
        # The group fighting on: the ended fight's END_COMBAT and the last
        # hit on its enemies since (None when it has stopped), and how many
        # hits the fight took
        self._ended_ms: int | None = None
        self._last_on: int | None = None
        self._fought = 0

    @property
    def fighting_on(self) -> bool:
        """Whether the group may still be fighting on the ended fight's
        enemies (not stopped yet)."""
        return self._last_on is not None

    def keep(self, hit: GroupHit) -> None:
        """A hit dealt after END_COMBAT that is not the group fighting on.
        While it may be, every hit since END_COMBAT is kept: a fight that
        turns out to carry on takes them all (carried_on)."""
        hits = self._hits
        hits.append(hit)
        horizon = hit.timestamp - fight_opener.OPENER_WINDOW_MS
        if self._ended_ms is not None:
            horizon = min(horizon, self._ended_ms)
        while hits[0].timestamp < horizon:
            hits.popleft()

    def fought_on(self, enemy: EnemyInfo, timestamp: int) -> bool:
        """A hit of the group's on *enemy* at *timestamp*, after END_COMBAT:
        whether it is the group fighting on, which the ended fight counts
        (on its encounter, as a hit in it): an enemy that fight hit, within
        FIGHT_ON_MS of its END_COMBAT or of the last such hit."""
        last = self._last_on
        if last is None or enemy not in self._ended or timestamp - last > FIGHT_ON_MS:
            return False
        self._last_on = max(last, timestamp)
        self._fought += 1
        return True

    def due(self, now_ms: int) -> bool:
        """Whether the group has stopped fighting on by *now_ms*, a log
        line's time: FIGHT_ON_MS without a hit on the ended fight's
        enemies."""
        return self._last_on is not None and now_ms - self._last_on > FIGHT_ON_MS

    def stop(self) -> bool:
        """The group has stopped fighting on, or combat began again, or the
        zone or the session changed: whether the ended fight took hits since
        its END_COMBAT, which its entry then counts."""
        fought = self._last_on is not None and self._fought > 0
        self._ended_ms = self._last_on = None
        self._fought = 0
        return fought

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

    def settled(self, hit_enemies: Iterable[EnemyInfo], ended_ms: int) -> None:
        """A listed fight of BLIP_MS or more ended at *ended_ms* and took its
        hits: the waiting starts again, a later line leaves the enemies it
        hit (*hit_enemies*, the records) to it, and the group may fight on
        them."""
        self._hits.clear()
        self._ended = frozenset(hit_enemies)
        self._ended_ms = self._last_on = ended_ms
        self._fought = 0

    def carried_on(self, ended_ms: int) -> list[GroupHit]:
        """The fight that ended at *ended_ms* carries on (the engine's
        COMBAT_RESUME_MS and FIGHT_ON_MS): the hits since that waited here
        are its own now, returned for its encounter, which has the group
        fighting on already. The earlier ones, a blip's, wait on, and the
        ended fight stays."""
        since = [hit for hit in self._hits if hit.timestamp >= ended_ms]
        self._drop_since(ended_ms)
        self._ended_ms = self._last_on = None
        self._fought = 0
        return since

    def listed_late(self, ended_ms: int) -> None:
        """A combat held for want of an enemy, ended at *ended_ms*, is
        listed after all: its entry is built from its encounter, which has
        the hits since."""
        self._drop_since(ended_ms)

    def reset(self) -> None:
        """A zone change or a new log session: unit ids start over."""
        self._hits.clear()
        self._ended = frozenset()
        self._ended_ms = self._last_on = None
        self._fought = 0

    def _drop_since(self, ended_ms: int) -> None:
        self._hits = deque(hit for hit in self._hits if hit.timestamp < ended_ms)


def take_damage_figures(entry: FightHistoryEntry, rebuilt: FightHistoryEntry) -> None:
    """The group fought on after the fight's END_COMBAT: the entry frontends
    hold takes from *rebuilt*, the fight built again with those hits, the
    figures its damage decides (FOUGHT_ON_SLOTS, each row's ROW_DAMAGE_KEYS
    and the rows' order) and keeps the rest as END_COMBAT left it. A row
    only *rebuilt* has, a player who came after the fight, is left out.
    The rows stay the same dicts, a key written at a time, since the
    engine holds them for a mastery found later in the session and the
    frontends read them without a lock; the list is a new one."""
    for slot in FOUGHT_ON_SLOTS:
        setattr(entry, slot, getattr(rebuilt, slot))
    rows = {row.get('unit_id'): row for row in entry.players}
    players = []
    for new in rebuilt.players:
        row = rows.pop(new.get('unit_id'), None)
        if row is None:
            continue
        for key in ROW_DAMAGE_KEYS:
            if key in new:
                row[key] = new[key]
        players.append(row)
    entry.players = players + list(rows.values())
