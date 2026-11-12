# Design notes

How ESO Log Tail solves the problems that are not obvious from the code's
shape: what the encounter log really carries, which game data is trusted
for what, and the rules chosen after measuring real logs. Every note here
is the docstring or a tagged comment of the code it describes, collected by
`scripts/build_design_doc.py`; edit the code, then rerun the script. The
link under each note is where it lives.

## The encounter log: unit states and effects

### ESOLogAnalyzer._handle_effect_changed

*[src/esolog_tail.py:3730](../src/esolog_tail.py#L3730)*

A buff or debuff coming, going or refreshing: the tracked effects
(every item of the uptime line), the timeline strip's built-in rows, and
enemy health.

Design: an EFFECT_CHANGED line is ``changeType, stackCount,
castTrackId, abilityId, <sourceUnitState>, <targetUnitState>``. A
unit state is ten fields (unitId, health, magicka, stamina,
ultimate, werewolf, shield, x, y, heading), so the source's id is
fields[4] and the target's fields[14]; the target state is a single
"*" when the effect is on the source itself. Reading the target from
the wrong offset (fields[10], the source's shield, nearly always
"0") made every group buff look as if it were only ever on its
caster, so the one reader, extract_effect_fields, serves every
consumer here. Enemy health is read from the target state when the
target is explicit and from the source state when it is "*"; the
source state's health is never the target's.

## Fight boundaries: fights the game cuts in two

### Fights the game cuts in two

*[src/esolog_tail.py:94](../src/esolog_tail.py#L94)*

The game ends and restarts combat in the middle of a fight, most often when the logging player is resurrected: END_COMBAT, then BEGIN_COMBAT a moment later. 48 logs of April to October 2026 held 53 such pairs, 0 to 484 ms apart, 45 of them straight after the player accepted a resurrection. A BEGIN_COMBAT this soon after END_COMBAT continues that fight when an enemy the group hit in the fight's last seconds is still alive; none of the 51 pairs between half a second and three seconds apart was the same pull. Later than that, it continues a boss fight when the group has fought on its enemies since and is still hitting one of them (waiting_hits.FIGHT_ON_MS, issue #162).

### ESOLogAnalyzer._continues_last_fight

*[src/esolog_tail.py:2163](../src/esolog_tail.py#L2163)*

Whether a BEGIN_COMBAT at *timestamp_ms* carries on the fight that
just ended instead of starting one: it follows the END_COMBAT
closely and an enemy the group was hitting when the fight ended is
still alive (see COMBAT_RESUME_MS), or, however long after, the
fight had boss damage, the group has fought on since and is still
hitting one, the same record, its last hit since END_COMBAT and
within FIGHT_ON_MS (waiting_hits).

### ESOLogAnalyzer._resume_last_fight

*[src/esolog_tail.py:2194](../src/esolog_tail.py#L2194)*

Reopen the encounter END_COMBAT closed. Its damage, deaths and
players are kept, and the entry frontends already have is brought up
to date when the fight ends (see _publish_fight).

### A death just after END_COMBAT

*[src/esolog_tail.py:88](../src/esolog_tail.py#L88)*

The blow that kills the last player standing ends combat, and that player's death event is written after END_COMBAT (about 85 ms later in live logs). A player death this soon after END_COMBAT belongs to the fight that just ended.

## Fight boundaries: combat with no enemy

### ESOLogAnalyzer._note_enemy_met

*[src/esolog_tail.py:2391](../src/esolog_tail.py#L2391)*

A combat event of *result* and *hit_value*, or a cast
(fight_opener.CAST, value 0), at *timestamp_ms*, with each unit's
'current/max' health on the line: the fight it falls in met an
enemy when it passed between the group (a player, a player's pet or
companion) and an enemy (a hostile unit, never a companion or a
released pet, see _opener_enemy). The group's line on an enemy
counts whatever its result or value, but on a dead one only the kill
(a hit above 0, or DIED_XP); an enemy's line on the group counts as
the opener counts a monster's act (ENEMY_ACT_RESULTS): not from a
dead enemy, and not a mechanic (fight_opener.is_mechanic).

Design: Combat with no enemy in it. The game enters combat for more
than enemies: for the group's weapon enchants, area damage and heavy
attacks on a neutral unit (Vateshran Hollows' Brimstone Orbs, broken
to cross the lava, or a Tomeshell in the Infinite Archive), for the
hits of a neutral trap (the Aetherian Archive's Shock and Frost
Traps), a unit the log never added (Cradle of Shadows' Pull of
Darkness), a hazard (the Infinite Archive's Molten Destruction), the
Arcane Knot's Temporal Splinters or a dead boss's poison, or for
nothing the log shows (two half-minute spells in Sunspire with no
combat event at all). Each ends with END_COMBAT and was listed as a
fight with nothing in it. Over the 395 split logs of January to
November 2026 that hold fights (9,023 of them), 58 in 29 logs met no
enemy from 10 s before BEGIN_COMBAT (since the last fight ended, as
the opener reads it, see fight_opener) to END_COMBAT: none had a hit
on an enemy or a player's death, 13 took damage, 15 lasted under a
second. Such combat is held back at END_COMBAT and never listed,
unless a player died in it or dies just after it ends (see
LATE_DEATH_GRACE_MS): a death to a trap keeps its fight and recap.
A trial's END_TRIAL in or after one goes to the last fight listed
(_trial_won_before_held): in one Lucent Citadel run it came 9 s
after Xoryn died, in an Arcane Knot combat, and now sits on Xoryn's
fight. Replayed with this rule, that was the only change to the
entries of the fights still listed. The 10 s before the line count
because the group's first hits often land before it: a survey of
combat events found 30 fights that met an enemy only there, none
with damage of its own (the hits went to the fight before; since
issue #162 a fight counts its hits from those 10 s, see
waiting_hits). A cast counts as the opener's does: five
of the survey's empty fights stay listed for a monster's cast at a
player or a player's at a boss, acts the opener names.

## Fight boundaries: the hits before the line and the group fighting on

### src/waiting_hits.py

*[src/waiting_hits.py:1](../src/waiting_hits.py#L1)*

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

## The fight's opener

### src/fight_opener.py

*[src/fight_opener.py:1](../src/fight_opener.py#L1)*

Who opened the fight, and with what (engine side, no Qt). Issue #159.

Design: the fight's opener is the first hit or taunt by a player, a
player's pet or a companion on a hostile enemy, named by the ability or
effect that damaged or taunted. Until 0.29 the fight pane put a `*` after
the player who dealt the fight's first damage after BEGIN_COMBAT. A survey
of 393 split logs (8,816 fights, January to October 2026) showed why that
mark was often wrong, and what a line could say instead.

BEGIN_COMBAT is the logging player's line, not the group's. The game writes
it when the logging player's client enters combat, and a group member's hit
usually lands a moment earlier: a player hit or taunt came before the line
in 4,243 fights (48.1%), a median 14 ms early, and the opener itself landed
before the line in 4,080 of 7,204 player-first fights. Such a hit fell on
the previous, finalized encounter, and the new one never saw it except in a
zone's first fight, so the star marked someone other than the opener in
1,385 of 7,176 player-first fights (19.3%; 32.6% in trials). The recorder
therefore reads a bounded memory of the moments before the line: the
settled acts of the last OPENER_WINDOW_MS (10 s) after the previous
END_COMBAT, ZONE_CHANGED or BEGIN_LOG. The fight's clock does not move: the
fight time stays BEGIN_COMBAT to END_COMBAT. Since issue #162 the figures
read the same moments: the group's hits in them count in the fight at their
own times, unless the fight before had hit the same enemy, or the enemy
died or left before the line (waiting_hits).

A millisecond is judged whole. Acts are buffered until the log moves past
their millisecond, since fan-out casts, shield-absorb pairs and taunt ties
need all of it; within it, line order decides. BEGIN_COMBAT adopts the
pending millisecond (1,294 openers sit in the line's own millisecond,
written before it), and END_COMBAT settles it into the fight before the
fight is built.

A quarter of openers taunt (1,822 of 7,204; 43.3% in trials). The game
writes a TAUNTED that shares its cast id with the taunting skill's cast and
hits; it can trail the hit by a millisecond (173 of 5,382 hit openers had
the same player's TAUNTED 1 to 5 ms later). So the opener is a taunt when
the same unit's TAUNTED lands in its millisecond, or carries its cast id
within TAUNT_TIE_MS; a TAUNTED before any counted hit opens by itself, and
another player's never counts.

Naming. A hit is named by its own ability. The pressed skill comes from the
cast's BEGIN_CAST, kept by cast id, and is added only when its name
differs: compared by id, 2,695 of 7,122 opening hits would print "Razor
Caltrops, from Razor Caltrops" (a DoT tick carries another id than its cast
under the same name), while 189 are real renames ("Concussion, from
Elemental Susceptibility"). A DAMAGE_SHIELDED line names the absorbing
shield, not the attack; the attack is the line after it with the same cast
id, source, target and millisecond, carrying the rest of the damage or 0.
An absorb is named by that partner, else by its cast's BEGIN_CAST, never by
the shield. A hit counts only above 0, as in the dps rules.

A monster acted first in 1,545 fights (17.5%, a lower bound). The log has
no threat or aggro line, and the addon API has none either, so a fight
started by walking into a monster's range cannot be told from a ranged mob
opening on sight. What the log does show is that a monster acted before
anyone hit or taunted, and whom it went for: a hostile's BEGIN_CAST names
its target, and so does its COMBAT_EVENT. The line says exactly that and
never "pulled". The monster's act is kept only when the opener comes
OPENER_MONSTER_MARGIN_MS (100 ms) or more later: inside it sit same-moment
races and Tideborn Taleria's Slaughterfish pulls (186 fights). When a
player had already begun a cast at a living enemy before the monster acted
(507 fights by a recount over the logs, 191 of them only before the line),
"first" would be false, so the line names the cast instead.

Noise is never the monster's opening. A naive rule would be wrong in 1,009
fights (11.4%): a dead monster's lingering area or DoT still "hits" players
after its DIED_XP (its health on the line is 0, 859 fights first); a hazard
is a unit named as its ability (Scorching Barrier, 119); a scripted cast
reaches three or more players in one millisecond (Nahviintaas' Look At, 23);
a DOT_TICK is an effect applied earlier (8). A few scripted mechanics pass
every filter and are listed by monster id (the Arcane Knot of Lucent
Citadel, whose Temporal Splinters opened 40 fights while the first player
hit came a median 13 s later; the second Tideborn Taleria unit that throws
the Slaughterfish Attack) or by ability id (Look At, Music Musicer). A unit
that ever had a player owner is not a monster: a released pet turns
HOSTILE with owner 0.

The memory's edge. A candidate whose enemy died or left before the line is
dropped (a hit's or cast's target, a monster act's source): it belonged to
the last pack, and the fight's figures leave its hits out too. An opener
within EDGE_AFTER_START_MS of the line that started the memory, or in the
window's oldest second, may not be the first act at all, so the line drops
"first" and the time there: "@tank was already fighting Yokeda Kai
(Goading Throw) when the fight began".

Times. The line's first act gets ", 2.0 s into the fight" or ", 4.4 s
before the fight's start" only from TIME_SHOWN_MS away from the line, so a
median lead of 14 ms reads as no time at all and nothing prints "1.0 s";
an arena's first seconds are its spawn, so an arena line never says "into
the fight". A monster-first opening's player line gets ", 5.8 s later".

## Starting mid-session

### LogFileMonitor._load_latest_session

*[src/esolog_tail.py:5877](../src/esolog_tail.py#L5877)*

Replay the log's most recent session up to the attach point.

Gives a mid-session attach the same state as having run since the
session began: full roster, this session's fights in history, and
the session's split file (created only if absent). Best-effort:
failures leave plain tailing.

Every session is replayed whole, however large. Until issue #107 one
over 768 MB got only the roster-only preamble sweep, which is not
enough: who owns which companion and pet is learned from the rest
of the session, and fights rebuilt that way differed in every one
of 18 measured on a Dreadsail Reef split. The sweep is left for a
session whose BEGIN_LOG is beyond the 2 GB lookback, and for a
replay that fails.

## Log freshness

### src/log_freshness.py

*[src/log_freshness.py:1](../src/log_freshness.py#L1)*

Log freshness derivation: when was the newest entry written to an encounter log?

Every ESO encounter log line starts with a relative millisecond offset from the
session's BEGIN_LOG event, and each BEGIN_LOG carries a Unix epoch (ms):

```
    5,BEGIN_LOG,1755729685851,15,"NA Megaserver","en","eso.live.11.1"
    43016,COMBAT_EVENT,DAMAGE,...
```

latest entry time = most recent BEGIN_LOG epoch + last line's relative offset.

Derivation is exact when a BEGIN_LOG is reachable, and falls back to the file's
mtime (marked "approximate") otherwise. Logs can reach tens of GB, so the
backward BEGIN_LOG search is capped rather than unbounded.

## Roles

### infer_player_role

*[src/esolog_tail.py:377](../src/esolog_tail.py#L377)*

Infer player role (T/H/D) from resources, weapon and healing heuristics.

A player whose largest pool is magicka is a healer when they have a
restoration staff equipped, or when they healed other players for more
than the damage they dealt (which still finds a healer whose staff the
bundled list does not know yet).

Args:
    player: PlayerInfo with max_health, max_magicka, max_stamina
    player_damage: Total damage dealt by this player
    player_healing: Total healing done to OTHER players
    skill_line_role: Role from ability-based inference (fallback)
    restoration_staff: Whether a restoration staff is on either bar

Returns:
    'T' for tank, 'H' for healer, 'D' for DPS

## Class skill lines and subclassing

### src/eso_sets.py

*[src/eso_sets.py:1](../src/eso_sets.py#L1)*

Which class skill lines a player has (subclassing).

Design: since Update 46 a character can swap any of its three class skill
lines for another class's, so the class id in UNIT_ADDED no longer says
what a build is. Two things in the log do.

The passives. The first list on a player's PLAYER_INFO line is their
long-term effects, and among the mundus boon, food and set auras it carries
every class-line passive the character has learned, by ability id. A
character with Assassination, Herald of the Tome and Animal Companions
lists Hemorrhage, Executioner, Splintered Secrets, Advanced Species and so
on. Each passive belongs to one line, so the lines are read off the ids
with no guessing: skill_lines_of looks each id up in
data/skills/class_passives.json (UESP's player skill table cut down to the
203 class passives by scripts/generate_class_passives.py, masteries
included) and names a line for every passive found. The lookup is by id,
never by name or icon: the group's Combustion resource return, the Reusable
Parts ally effect and the Resolute Defense proc share a passive's name and
land in the same list, and a passive's icon does not tell it from an active
(Blessing at the Peak uses an ability_* icon). Both rank ids of a passive
are in the table; a character lists the rank they have.

The slotted abilities, as a filler. ESOSubclassAnalyzer matches the names
of the bar abilities (ABILITY_INFO) against SKILL_LINE_ABILITIES, every
class line's ultimate, actives and morphs as the game names them, exactly
(never by substring: "Carve" is Two Handed, not Fatecarver; "Swarming
Scion" is Vampire, not a Warden Swarm), and the lines with the most matches
win. It cannot see a line the player slotted nothing from, which is routine
for healers, tanks and Arcanist DPS, and the passives can miss a line whose
passives a mid-level character has not learned yet. So skill_lines_of takes
the passives' lines first and fills up to three from the slotted guess.
In 73 split logs of September and October 2026 (7,019 distinct builds) the
passives named exactly three lines for 98.5% of builds and never
contradicted the slotted guess, which had missed one or more lines in 56%
of them; 489 builds borrowed a line, and for 133 of those the lines shown
change, 18 of them borrowed purely for the passives (nothing slotted). A
character has at most three lines, since subclassing swaps lines and never
adds a fourth; a fourth line of passives, seen three times in the survey,
loses to the lines whose actives are slotted.

The fight view and build window show only the borrowed lines, each with a
plus sign before its first word ("NB +Herald" for a Nightblade who swapped
a line for Herald of the Tome), so a stock build shows just its class. A
player whose class is unknown shows every line found.

Class Mastery passives (five per class; only a character with all three of
its own lines can take them) take the same place beside the class, after a
colon ("NB: An Eye for Exploitation, Above and Beyond"), and are named on
the build window's mundus and food line too. The PLAYER_INFO list names
only some of them, because it holds only the passives whose effect is always
on: a mastery that works by a proc (Unbound Potential, Abyssal Emergence,
Wildfire Embers, Bright Harbinger...) is never in it. Such a mastery shows
in the log as an EFFECT_CHANGED the player is the source of, under one of
a few effect ids that carry its name; the table lists those 60 ids as
mastery_effects, and mastery_of_effect names the mastery of one. The
engine notes a mastery on its holder when such an effect fires, and keeps
it for the rest of the session, since a mastery does not change between
fights. In the 73 survey logs, 11,697 pure-class player rows: the list
alone named a mastery for 42% of them, the list plus the fight's own
effects for 79%, the list plus the session's effects for 90% (191 of 209
characters). Nine of the 35 masteries fire no effect of their own name;
for four of them the effect is named after the buff it grants and has an
id in the same block, sourced by one class alone in those logs: Lead from
the Front's Major Berserk and Major Protection (Dragonknights), Tundra's
Maw's Major Brittle and Bountiful Harvest's Major Heroism (Wardens), and
Cutthroat's Focus's Cutthroat's Mockery (Nightblades). The table carries
those as signature effects (scripts/generate_class_passives.py says how
each was pinned down), and mastery_of_effect checks the source's class for
them.

Three of the other five give resources and fire no effect at all, only the
gain: a COMBAT_EVENT POWER_ENERGIZE whose source is the holder, under an id
carrying the mastery's name (Conservation of Energy's Magicka and Stamina
to the Sorcerer, Nocturnal Inspiration's Ultimate to the Nightblade, Share
the Spoils' Magicka, Stamina and Ultimate to the Nightblade's group). The
engine reads a mastery from those as well. In 103 split logs of September
and October 2026, every POWER_ENERGIZE under a mastery id, about 244,000
lines over twelve ids, came from a player of that mastery's class.
Devout Guardian's shield is an effect called Hold the Line, kept as a
signature effect. Bastion of Light alone stays invisible: it heals through
Sacred Ground and gives Ultimate, and nothing in the logs names it.

The game lets a character take two masteries ("selecting two passives",
its own text). A third shown beside the class means an id fired for
someone who does not hold its mastery. Font of Power's 263878 has: three
or four gains late in a session from Sorcerers whose Calculated Defense
and Conservation of Energy fire from the first minutes to the last; most
sessions that show Font of Power show dozens to hundreds of gains.

Cycle Unending's effect (263532) is the one a pet fires: its source is the
Necromancer's Blighted Blastbones, Skeletal Archer or Grave Lord's
Sacrifice, and it lands on their owner (220 of 239 gains in twelve logs).
So the engine credits a mastery effect whose source is a player's pet to
that player (the encounter's pet_ownership). Before, 84% of Necromancer
rows showed one mastery, and no Necromancer damage dealer ever showed two;
in a replay of the 103 split logs of September and October 2026 the
change added Cycle Unending to 792 rows, all Necromancers, none of them
gaining a third, and nothing else in any fight changed (issue #149).

A character can take two masteries (MAX_MASTERIES), and a row often shows
one. After that change, 1,581 of 13,818 pure-class rows (11%) in those
logs did: 915 were fights before the second showed later in the same log,
since a proc mastery is known only once it fires (Booming Voice was never
on a session's first fight, Erudite's Rigor on 16% of them, Abyssal
Emergence 39%, Bright Harbinger and Lead from the Front 43%); the rest
came from 59 characters' logs in which it never showed, Templars the most
(Bastion of Light is never logged). Two things follow. The engine fills a
mastery it finds into the player's earlier fights of the same BEGIN_LOG
session, on rows that show fewer than two, and announces each of those
fights again: a mastery does not change within a session, which is why it
is kept for the rest of it. That leaves 674 rows (5%) showing one, none of
them before a second that shows later; Templars 23% of theirs, Sorcerers
18%, every other class 6% or less. And where one still shows, the fight
pane and build window say a second is likely, listing the class's others
the likeliest first for the player's role (likely_masteries, from the
file's mastery_order; the generator says how the order was counted); a
mastery the log never names is listed last and marked
(masteries_never_logged).

## Ability icons and ESO-Hub links

### src/ability_icons.py

*[src/ability_icons.py:1](../src/ability_icons.py#L1)*

Ability icons and ESO-Hub skill links: engine-side helpers (no Qt).

The encounter log names every ability's icon in its ABILITY_INFO line
("/esoui/art/icons/ability_arcanist_002_b.dds"). The app ships one PNG per
ability icon under data/icons/abilities (built by
scripts/extract_ability_icons.py from the installed game), so an icon is
resolved purely by that filename's stem; nothing is downloaded at runtime.

ESO-Hub page links come from data/esohub/ (built by
scripts/generate_esohub_links.py from ESO-Hub's sitemaps): a logged ability
name is slugified the way ESO-Hub slugs its pages and looked up in
skills_en.json; a LibSets set name is looked up as-is in sets_en.json. A
scribed skill ("Shocking Banner") and its scripts ("Lingering Torment") are
looked up by slug in scribing_en.json. Unknown names get no link.

### src/gui/icon_cache.py

*[src/gui/icon_cache.py:1](../src/gui/icon_cache.py#L1)*

In-memory cache of bundled ability icons for the fight view.

Icons are PNG files under data/icons/abilities, one per game icon stem
(see scripts/extract_ability_icons.py). Each image is read from disk once
and kept as a QImage; a miss is remembered too, so an ability with no bundled
icon costs a single stat() per session and then renders as text. An icon can
also be had with a colored ring drawn inside its edge (the fight view marks
the abilities a player taunted with that way); each ring color is drawn once
per icon.

### scripts/extract_ability_icons.py

*[scripts/extract_ability_icons.py:1](../scripts/extract_ability_icons.py#L1)*

Extract ESO ability icons from the installed game and convert them to PNG.

Why: the encounter log names every ability's icon
(ABILITY_INFO ... "/esoui/art/icons/ability_arcanist_002_b.dds"), so the app
can show icons offline if it ships one PNG per icon found in the game files.
Three families are extracted: ability_*.dds (player skills, for the ability
bars), death_recap_*.dds (what monster attacks use, for death recaps), and
the skill icons an update named after itself, u<NN>_ability_*.dds: Update 50
gave five werewolf skills u50_ability_werewolf_* icons, and Crypt Transfer
has had u38_ability_armor_ultimatetransfer since Update 38. A slotted skill
whose icon belongs to no such family is named in DEFAULT_STEMS: Rampage, what
the werewolf ultimate becomes at full Fury, uses an achievement icon. Run
this after each ESO update to refresh that set.

Requirements (Windows):
  * EsoExtractData v0.53+ by UESP: https://en.uesp.net/wiki/ESO_Mod:EsoExtractData
    Pass --extractor, set ESO_EXTRACT_DATA, or keep it at D:\extract-eso\.
  * Pillow for the DDS -> PNG conversion (pip install -r requirements-build.txt).
  * An installed, patched ESO client (its depot\eso.mnf). Pass --eso-dir, set
    ESO_INSTALL_DIR, or let the script probe the usual Steam/Zenimax paths.

Pipeline:
  1. Dump eso.mnf's file table without extracting anything (-k -m, ~4 s).
  2. Find every \esoui\art\icons\<prefix>*.dds row and merge their table
     indexes into a few dozen -s/-e ranges (a small gap of unrelated files is
     cheaper than another ~3 s MNF reload; -n only matches exact names).
     The extractor's -s/-e counter is offset from the table's Index column
     (2,337 on the Update 49 client), so two one-file probes calibrate it.
  3. Extract those ranges to a temp folder. Extracted files are numbered by
     table Index (<archive>\<Index>.dds), which the table maps back to names.
     Convert the matching .dds files to PNG at --size px, write
     <out>/manifest.json and report what changed against the previous
     manifest. Optionally (--check-log) verify that every icon slotted on a
     bar in an Encounter.log exists in the output.

The game folder is only read. Temp output is deleted unless --keep-temp.

## Scribed skills and their scripts

### src/scribing.py

*[src/scribing.py:1](../src/scribing.py#L1)*

Scribed skills: which scripts each player wrote into their grimoire skills
(engine side, no Qt).

A scribed skill is a grimoire (Banner Bearer, Wield Soul, ...) with a focus,
a signature and an affix script. The grimoire and the focus script give the
skill its name ("Shocking Banner" is Banner Bearer with Shock Damage); the
signature and affix scripts add effects that the name does not show. The
encounter log lists all three scripts after the two flags of the skill's
ABILITY_INFO line:

```
    ABILITY_INFO,217699,"Shocking Banner","/esoui/art/icons/ability_grimoire_support.dds",F,T,"Shock Damage","Class Flourish","Heroism"
```

The grimoire is not named, but every grimoire has its own icon (GRIMOIRES).

What the log does, as far as four logs from September 2025 to October 2026
show (225 ABILITY_INFO lines with scripts):

- An ability id does not identify the skill. One id covers several focus
  scripts of a grimoire (217699 is Fiery, Fortifying, Magical, Restorative,
  Shocking and Sundering Banner), so the name and the scripts of a bar slot
  belong to the player, not to the id.
- The game writes each (ability id, scripts) combination once per BEGIN_LOG
  session, directly before the PLAYER_INFO of the first player seen with it
  (0-1 ms earlier, with only other ABILITY_INFO lines in between). That
  PLAYER_INFO is how a combination is tied to a player.
- The game also writes the skill without scripts, as an ordinary
  seven-field line, once per session and id. Most of these lines come at
  another moment (46 of 60 in the October 2026 log, presumably when the
  skill is first used). The rest sit directly before a PLAYER_INFO, for a
  player whose scripts the game does not have; for 10 of those 11 players
  the scripts followed before a later PLAYER_INFO, 0 to 206 s on.
- A later player whose line was already written, with or without scripts,
  gets no line of their own. Their skill is then one of the lines written
  for that id: certain when there is one, otherwise a short list of options.
  The same holds for a player who re-scribes to a combination already
  written in the session; the log gives no sign of that change.

The approach follows the ESO Log Tool (github.com/sheumais/logs), which
renames scribed skills to "Name (Signature / Affix)" before uploading logs.

## Werewolf form: the bar the log never writes

### src/werewolf.py

*[src/werewolf.py:1](../src/werewolf.py#L1)*

Werewolf form: the bar the log never writes, and the ultimate it renames
(engine side, no Qt). Issue #17.

Design: since Update 50 a werewolf's skills sit on a bar of their own, which
the game switches to on transforming. PLAYER_INFO writes only the two human
bars, so a player who spends a fight in form shows bars they never used. Of
1,068 PLAYER_INFO rows written while a player was in form (55 split logs of
July to October 2026, client versions 12.0 and 12.1, about 25 characters),
1,053 carry the human bars. The other 15, from two anonymous players on
12.0, carry the werewolf bar in place of the front bar, in the slots' real
order and agreeing with their casts. A Rockgrove log of 2026-10-24 (client
12.1, issue #49) showed a third shape: all 11 rows of one player list a
single bar as both the front and the back bar, three werewolf skills beside
Razor Caltrops and Inner Fire, while the player, in form the whole log,
cast Hircine's Rage and Ferocious Roar in every fight and never those two.
The form is one bar of five skills with no swap, so that bar was stale. A
logged bar holding three or more werewolf skills (``is_werewolf_bar``) is
therefore no human bar and no trusted werewolf bar: the engine drops it
before anything reads it, and the werewolf bar is rebuilt from casts for
every werewolf alike. A human bar can hold one werewolf skill for its
while-slotted bonus (Hircine's Fortitude on one player's front bar, 18
rows), which the threshold spares. Werewolf players spent 1,234 of their
1,524 fights of 5 s or more wholly in form, 110 partly, and 180 not at all.

The bar is rebuilt from casts. Each werewolf skill is cast under the id of
the skill its slot holds, one id for all four ranks, with one exception:
within close range a Pounce morph becomes its Carnage version, cast from
the same slot, so SLOT_SKILLS maps Carnage, Brutal Carnage and Feral
Carnage to their Pounce. Feeding Frenzy is not a slot: it is Roar's
synergy, which every group member activates. The light and heavy werewolf
attacks and Devour are not slots either, though they prove the form. Of 58
player sessions with werewolf casts, 55 cast exactly five distinct bar
skills, three cast fewer, and none ever cast a sixth or two morphs of one
skill, so the casts of a whole session can be pooled. A fight's own casts
show the whole bar in only 58% of fights; the session's casts up to the
fight's end show it in 94%, which is the rule here. In the two 12.0 cases
where the game logged the werewolf bar, the rebuilt bar agreed with it; in
the 12.1 case the casts were right and the log was not. Casts
say nothing of the slots' order, so the bar follows the skill line's order
(LINE_POSITION): Pounce, Hircine's Bounty, Roar, Gnash, Rending Claws. A
skill slotted but never cast stays unknown.

The form itself is a hidden effect, 39038 "Werewolf Transformation", plus
the morph's own effect (47083 Werewolf Berserker, 47069 Pack Leader, 47028
for the unmorphed transformation in older logs). On client 12.1, 39038 is
on for 99.9% of in-form casts and for none of the casts of human-bar
skills. A log that starts mid-form has no GAINED: the werewolf casts are
the only sign, and the form is taken to have begun with the session. Death
does not end the form: after 241 of 251 deaths in form the player's next
skill was a werewolf skill, with no new transformation logged.

The ultimate: the unit state's werewolf field is Fury, from 0 to 1000. At
full Fury the transformation ultimate becomes Rampage, or Enduring Rampage
for Pack Leader, and PLAYER_INFO then lists that in the slot, but only for
the player who writes the log. For that player, 170 of 171 fight starts in
form with full Fury listed Rampage, and 1 of 181 other starts did. For
group members, 0 of 424 such starts did. So Rampage in a bar is the morph
caught at full Fury, and the bar shows the morph instead (``stand_in_for``):
the player's active morph effect names it, else the morph slotted in their
earlier rows, else STAND_INS. The client names more Rampage ids than the
two seen in a slot; the unseen ones are left unmapped.

Icons: five of the werewolf skills (Pounce, Brutal Pounce, Feral Pounce,
Rending Claws, Claw Fury) carry Update 50 icons named u50_ability_*, and
Rampage an achievement icon, all outside the ability_* family the app used
to bundle (see scripts/extract_ability_icons.py).

## Cast counts and casts per minute

### src/casts.py

*[src/casts.py:1](../src/casts.py#L1)*

Cast counts and casts per minute (engine side, no Qt). Issue #94.

Design: every player's BEGIN_CAST lines are in the log, the group's as well
as the logging player's. One cast can write two of them under one
castTrackId: a channelled heavy attack writes one at the press and one for
the channel (11 of 11 for a Lightning staff in the Tideborn Taleria fight
of 2026-10-27), and a synergy can write two ability ids (Healing
Combustion, 63507 then 95042, on the same timestamp). A cast is therefore
one castTrackId per caster, whatever the lines under it.

Design: a track id written again after its END_CAST (issue #226). Over the
391 split logs of 2026 (5.3 million BEGIN_CAST lines), 388,764 lines reuse
a track id their caster had already used. Most are the same cast. A
channelled heavy attack's or a channel's later lines come with no END_CAST
between (145,778, 99.99% within 200 ms), and a synergy's or a multi-hit
skill's second line comes in the same millisecond. But 92,309 players'
lines, which the engine merged, came at a later millisecond after the
track's END_CAST, in two kinds:
- A synergy taken again under its first take's track id: Healing
  Combustion 477 times, Combustion 42. A new cast.
- A proc the game writes as an instant cast, never on anyone's bar, under
  the track id of its first tick, every tick: 91,230 lines. Meridia's
  Favor about every second (43,625), Highland Sentinel and Peace and
  Serenity every second, Blood Magic, the scribed banner's tick every five
  seconds, Grundwulf, Obsidian Stance.
A cast is a press (Chris's choice), so an ability its caster writes again
on its own track after END_CAST, at a later millisecond, is a proc for the
rest of the session: it leaves that caster's counts, the extras and casts
per minute, unless it is a cast of a skill on their bar, matched as the
slot counts are (on_bars): Chakram of Destiny, slotted as 186207, is
pressed as 194237 and pressed again on the same track. An extra (a light
or heavy attack, a dodge, a potion) is never a proc. Over the 391 logs the
rule finds 14 procs, all players' (none a companion's, an extra or a
werewolf skill). A proc is known from its second tick, so a fight whose
entry was built between its first two ticks keeps that first one: at most
one cast, once a session. Before, each proc counted once a fight, and a
synergy taken again not at all. A track still
written when a fight's entry is built carries over to the next fight:
the banner pressed in one fight ticks on in the next, and before, its
first tick there counted as a press (638 players' fights over the 391
logs, every one a Shocking, Magical or Fiery Banner). A cancelled cast's
END_CAST (PLAYER_CANCELLED) never reaches the engine, as the parser
rejects it, so a track id reused after one stays the same cast; a slotted
skill's own effect written later on its track (the banner's first tick, a
werewolf ultimate's form) stays with the press.

A fight's casts are those begun from its start to its end, the engine's
fight window (BEGIN_COMBAT to END_COMBAT). Combat Metrics counts the same
way: for the logging player in that fight it showed Force Pulse 37,
Subterranean Assault 12, light attacks (Lightning) 52 and every other skill
alike, and left out the pre-buffs cast in the ten seconds before the pull
(Blockade of Frost 7 in both). Its light attacks (Ice) read 15 against the
log's 14. Over 12 trial and arena splits (193 fights, 66,244 casts), 3% of
casts began in the 3 s before BEGIN_COMBAT; those are not counted.

A count sits under a bar slot when the cast's id is the slot's, or its name
is (Venom Skull is slotted as 117624 and cast as 123704, Incapacitating
Strike as 36508 and 113105, Crystal Fragments' instant proc is 114716), or
both are in one of the families of SKILL_FAMILIES. The Destruction Staff
families are there because the bar lists those skills under a base id
(Elemental Blockade 39011) or the element of the staff equipped when
PLAYER_INFO was written, while the cast
carries the element of the staff in hand: over the October splits,
Elemental Blockade was cast as Blockade of Fire 2,651 times, Frost 2,391,
Storms 1,257, and a bar listing Blockade of Storms was cast as Blockade of
Frost 253 times. A skill slotted on both bars shows its total under each
(Chris's choice: totals per skill, not per active bar).

One skill writes no BEGIN_CAST at all: the Arcanist's Fatecarver, matched
in 0 of 1,514 player-fights with Pragmatic Fatecarver slotted and 0 of 68
with Exhausting Fatecarver (no other slotted skill is systematically
unmatched; those that are never cast are slotted for their passives,
banners cast before the pull, or rarely used ultimates). Each use instead
gains its channel effects on the caster under one castTrackId: Pragmatic
writes 186369, 189533, 201265 and 201273 (6,867 casts in the October
splits; 201265 also comes alone, a shield), Exhausting 186780, sometimes
with 184291. CHANNEL_EFFECTS turns such a GAINED into a cast of the morph,
one per castTrackId like any cast. No log had the unmorphed Fatecarver.

Casts per minute counts every cast (Chris's choice), extras included,
over the fight's duration; a player who left during the fight over the
share of it they were there for.

The extras are the casts no slot holds, by kind (EXTRA_KINDS): light and
heavy attacks (every id the client's own name table, en.lang table
198758357 of Update 51, names "Light Attack (…)" or "Heavy Attack (…)"),
bashes, weapon swaps, dodges, synergies, potions and Break Free. The log
marks neither a synergy nor a potion: a synergy writes only its own
effects, and a potion is cast under its first trait's effect (Restore
Health, Major Brutality) with the generic icon Recall and Mount Up also
carry. Both come from the ids seen in the October splits: SYNERGIES holds
the skill-line synergies (class, guild, Undaunted, werewolf), not the
trials' mechanics; POTIONS the alchemy block 45221 to 45241, the vendor,
Alliance War and Crown potions. Werewolf light and heavy attacks count as
light and heavy attacks.

A companion's casts are counted the same way, under its row key
(companions.py) and over the whole fight (issue #130). Its light attacks,
block, dodge, bash and break free have ids of their own, none of them in
the player's sets (its light attacks are plain "Light Attack", one id per
weapon look), and it never heavy attacks, swaps weapons, takes a synergy
or drinks a potion: over 214 split logs with a companion its casts that
are not skills were those ids and Mount Up. So its extras line has kinds
of its own (COMPANION_EXTRA_KINDS), Block among them, which a player's
never needs (a player's block writes no cast), and a player's 'casts'
stays as it was.

Each cast the recorder keeps also holds the unit it was aimed at, named
as it is noted, and the time of the END_CAST its track wrote next, with
whether that said INTERRUPTED (issue #214): the Events tab's actions show
them, from the fight entry's packed copy (fight_casts). Nothing here
counts them, so the counts are as they were; cast_records gives the
counts' casts one by one.

## Magicka, stamina and ultimate spent and gained

### src/resources.py

*[src/resources.py:1](../src/resources.py#L1)*

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

## Companions: a row of their own under their owner

### src/companions.py

*[src/companions.py:1](../src/companions.py#L1)*

Companions: a line of their own under the player they belong to (engine
side, no Qt). Issue #74.

Design: a companion (Mirri, Bastian, Ember, Isobel, Sharp-as-Night,
Azandar, Tanlorin, Zerith-var) used to be one more pet: its damage and
healing were folded into its owner's figures. It is a character with its
own skills, health and deaths, so each companion that is out during a fight
now gets a row of its own on the group list, straight under its owner, with
the name and dps links a player's row has. A setting
(``companions.accrue_to_owner``, off by default, Chris 2026-10-27) also
counts its damage and healing as the owner's, as before; the group total
counts every hit once either way. Combat Metrics (LibCombat 89) counts the
player and their pets, COMBAT_UNIT_TYPE_PLAYER_PET, and never the game's
COMBAT_UNIT_TYPE_PLAYER_COMPANION, so the default also matches what a
player's own Combat Metrics shows them.

What the log writes, from a survey of the split logs (386 unique sessions,
October 2026):

- A companion is a MONSTER unit with a fixed monsterId per companion
  (COMPANION_MONSTER_IDS), no handle or character id, its companion level
  in the level field and a health pool only.
- The logging player's own companion is added with reaction COMPANION and
  ownerUnitId set to the logging player. Another member's is added as
  FRIENDLY with owner 0; a later UNIT_CHANGED names the owner, which
  track_pet_ownership reads for every pet. A companion is known by its
  reaction or its monster id.
- Another member's companion is nearly always added under the name
  "<handle>'s Companion" (141 of 150 such UNIT_ADDED lines in the October
  2026 splits; the logging player's own is always added under its own
  name). That handle can be one the log keeps from the owner: a player
  added with neither name nor handle (the engine's ``anon``) is named only
  by their companion in 217 file and handle pairs over 117 split logs,
  199 handles. Replayed, 65 companion rows read "@handle's Companion"
  straight under an ``anon`` row, and the name reached the buff timeline,
  the penetration casters and the death recaps.
- So the log's name for a companion is never used. Every companion, the
  logging player's own included, is "<owner>'s Companion" (shown_name;
  Chris, 2026-10-29): the owner's handle, or ``anon`` for an owner the log
  gave no handle, however many anonymous players there are, and for a
  companion whose owner is not known yet. The name follows the owner: it
  is set when the owner is (CombatEncounter.name_companions), and again
  when an anonymous owner is named on joining the group (presence.py,
  rule 6). The Hide names mask hides the owner part as it hides the
  owner's own name (gui.name_mask).
- A companion gets a new unit id every time it is summoned again (after a
  death, a zone change, a dismissal): four unit ids for one Isobel in a
  solo Moon Hunter Keep run of 2026-10-26, where she died five times, so
  its row is keyed by owner and monster id (row_key), not by unit id: the
  re-summons of one companion within a zone are one row.
- PLAYER_INFO never names a companion, so the log has no bar or gear for
  it. Its casts carry its own ability ids, whose icons are the game's
  ability_companion_* family (124 of them bundled): the row's bar is the
  skills it was seen casting this session, in first-cast order
  (bar_ability), the way werewolf.py rebuilds a werewolf's bar, with its
  ultimate set apart at the end (bar_order). Light attacks, block, bash,
  dodge roll and break free have other icons and are left out.
- A companion's death is a DIED line naming it as the dying unit; it is
  shown on its row, not counted in the fight's Deaths, which stay player
  deaths.
- Only 15 companion lines in 386 sessions fall inside a fight (trials while
  members leave, arena stage transitions, a solo summon at the pull); the
  rest come and go between fights.

The effect rules still see a companion as a pet (ESOLogAnalyzer._unit_kind),
so ``pets`` rules, the group size an expectation reads and the pen/crit
figures do not move with the companion rows.

Casts, ultimates and healing (issue #130), from a second survey of 214
split logs with a companion, January to October 2026, that forgets a
companion's unit id at its UNIT_REMOVED (the game hands those ids to
players later, and the first survey counted those players' casts as the
companion's):

- Every cast of a companion is a BEGIN_CAST under its unit id, as a
  player's is, so the cast counter (casts.py) counts a companion's casts
  under its row key: the re-summons of one companion are one row's casts.
  Besides its skills it casts light attacks, Block, Roll Dodge, Bash and
  CPN Break Free under ids of its own; it never heavy attacks, swaps
  weapons, takes a synergy or drinks a potion (casts.COMPANION_EXTRA_KINDS).
- Each companion has one ultimate (ULTIMATES). Each id was cast by its own
  companion's monster id only: 213 casts, Raging Storm 76, Impeccable
  Shot 63, Baneslayer 23, Blade of the Crossing 18, Gore 11, Vigorous
  Tentacular Eruption 10, Unleashed Rage 7, Ruinous Outburst 5.
- Every line a companion is the source of carries an ultimate pool out of
  500, and an ultimate costs about 200 of it; but the cost is not always
  written after the cast (a Baneslayer's own BEGIN_CAST often reads 0 or 1
  already), so the ultimates are counted by their cast ids, not from the
  pool. The other way round, every fall of 150 or more in a companion's
  pool is one of these casts: one in 214 logs is not within 4 s of one, a
  Raging Storm cost written 5.5 s late. So no ultimate goes unlogged.
- An ultimate is counted as any cast is, on its BEGIN_CAST. Of the 213,
  206 ended COMPLETED, one INTERRUPTED, one PLAYER_CANCELLED and five
  have no END_CAST (two with no effect, damage or cost: the fight ended
  under them), so the count can be about 2% over the ultimates that went
  off. The parser drops an END_CAST with a cancel reason, which a rule on
  the outcome would need.
- Its healing is the engine's healing to others
  (CombatEncounter.add_healing_to_player): the heals that landed on a
  player, its owner included; not its heals on itself or on pets, and not
  the overheal.
- Two skills carry the game's generic icon (Storm Barricade 157226 and
  Fire Barricade 157145, 42 casts in combat in the 214 logs), so
  bar_ability leaves them off the bar: they count in the casts and the
  cpm only. Sepulchral Chill writes a second id (213284, the generic
  icon) under its own cast's castTrackId, which the counter counts once.
- A UNIT_CHANGED that sets a companion's owner to 0 is it leaving: 189 of
  them, after which came 3 casts and 0.04% of companion damage. None cast
  in combat before its owner was known.

## Members who leave, come back, or come back on another character

### src/presence.py

*[src/presence.py:1](../src/presence.py#L1)*

Group members who leave, come back, or come back on another character
(engine side, no Qt). Issue #78.

Design: a group list should name the people who were in the fight, once
each. Before this, a member who left stayed on the list at 0 dps in every
later fight of the zone (656 of 9,435 fights in the split logs, 1,256 stale
rows), a member who came back on a new unit id got a second row, and a
member back on another character had no row in the fight they came back to
while their damage was in the group total. The rules below were chosen so
that a player with no UNIT_REMOVED and no second UNIT_ADDED in the zone
keeps every figure they had.

What the log writes, from 386 unique sessions (October 2026):

- ``Offline`` is a loading placeholder: a UNIT_ADDED named ``Offline`` with
  the handle and character id intact, replaced by the real unit (a new unit
  id) within 0 to 29 s. It is skipped.
- Leaving is UNIT_REMOVED. Coming back is always a fresh UNIT_ADDED: the
  same character keeps its character id, and its unit id only on an
  instance reload (a ZONE_CHANGED between, which starts the zone afresh
  anyway). Without a zone change the id is always new.
- Another character of the same account is the same handle with a new
  character id (and a new per-session id); its PLAYER_INFO comes at the
  next pull, or never. In 14 of 17 cases the old character's unit was never
  removed.
- A player's UNIT_CHANGED never changes who they are, except an anonymous
  member (empty name and handle) becoming named on joining the group.
- A departed player's unit id can be handed to a monster.

The rules (Chris, 2026-10-27):

1. A player is their character: handle and character id, the character id
   alone being unique. Rows stay per character.
2. UNIT_REMOVED marks the player gone (``left_at``). The fight in progress
   keeps their row, greyed, with the share of the fight they were there for
   (present_share); from the next BEGIN_COMBAT they are off the list. A
   MONSTER added on their unit id marks them gone too, and that id is no
   longer theirs.
3. The same character back in the zone is the same row: the new unit id is
   an alias of the record, so the damage before and after the drop goes to
   one row and its dps time spans both, the gap included (as Combat Metrics
   counts it). At the next BEGIN_COMBAT the record takes the new id as its
   own, its companion and pets following, so later fights are keyed as for
   anyone else.
4. Another character is a new row, and the old character is gone. Until its
   PLAYER_INFO arrives it has no build; it is listed anyway, with the class
   from UNIT_ADDED and empty bars, when the log says it is grouped with the
   logging player, so the fight's rows add up to its group total. Anyone
   else without a build stays off the list, as before (passers-by in the
   Infinite Archive and overland).
5. Offline stays skipped.
6. An anonymous member named by a UNIT_CHANGED takes that name and handle.
7. A companion follows its owner: its row is keyed by the owner's record,
   so a re-summon, or a summon on the owner's new unit id, is the same row,
   and it leaves the list with its owner.

What is per unit id and not merged in the fight a member comes back to:
the timeline strip, the uptime spans and the pen/crit buffs on them, which
the trackers keep by the unit id the log names. From the next pull they
are keyed as for anyone else.

## Builds: gear, weapon types, armor weights, mundus and food

### src/player_build.py

*[src/player_build.py:1](../src/player_build.py#L1)*

Player builds: the gear, mundus stone and food a player started a fight with
(engine side, no Qt).

The encounter log writes one PLAYER_INFO line per group member as combat
starts. Besides the two ability bars it lists the player's long-term effects
(passives, set auras, the mundus boon, food) and one entry per equipped item:

```
    slot, id, isCP, level, trait, displayQuality, setId,
    enchantType, isEnchantCP, enchantLevel, enchantQuality
```

```
    [MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,POISONED_WEAPON,T,16,LEGENDARY]
```

What 4,279 such lines from 32 logs of October 2026 show:

- Seventeen slot names occur. An empty slot is left out of the list, so a
  two-handed weapon is a main hand with no off hand beside it. COSTUME is
  cosmetic and skipped here.
- A slotted poison (POISON, BACKUP_POISON) is an item id and a quality. Its
  name comes from data/items/poisons_en.json, built by
  scripts/generate_poison_names.py.
- A mythic item is logged as LEGENDARY; only its set's LibSets type says it
  is mythic.
- The line is written once per fight, so a build is the one the player
  pulled with. Item names, weapon types and armor weights are not logged.

build_fields turns a player's line into the 'gear', 'mundus' and 'food' keys
of their fight-entry dict. The label functions name the log's values for
display; a value they do not know is shown in a readable form of itself.

Two things the log leaves out are looked up by item id in tables built from
UESP's item database. armor_weight says whether an armor piece is light,
medium or heavy (data/items/armor_weights.json, built by
scripts/generate_armor_weights.py). weapon_type says what a weapon or shield
is, an inferno staff or a dagger (data/items/weapon_types.json, built by
scripts/generate_weapon_types.py); has_restoration_staff puts the role
heuristic's question to it.

### scripts/generate_weapon_types.py

*[scripts/generate_weapon_types.py:1](../scripts/generate_weapon_types.py#L1)*

Generate data/items/weapon_types.json: the item ids of every weapon and
shield, one sorted list per type, for the Type column of the build window's
gear grid and for the healer role's restoration staff check.

The encounter log gives a weapon as an item id and never names its type
([MAIN_HAND,133257,T,16,WEAPON_CHARGED,LEGENDARY,361,...]). UESP's item
database lists every weapon and shield with its type in one request (about
63,000 items, 2.5 MB). Each type's ids are kept here under the name the game
uses for the type (an inferno staff, a battle axe, a shield).

Checked against 20 logs of October 2026: all 174 weapon ids in them were in
UESP's list. A weapon from a set added to the game after this file was built
shows a dash in the build window until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_weapon_types.py
A reply from UESP already saved to disk can be used instead of fetching it
again (UESP asks for sparing use of its export):
    python scripts/generate_weapon_types.py --from <saved reply>.json

### scripts/generate_armor_weights.py

*[scripts/generate_armor_weights.py:1](../scripts/generate_armor_weights.py#L1)*

Generate data/items/armor_weights.json: the item ids of every light, medium
and heavy armor piece, for the Weight column of the build window's gear grid.

The encounter log gives an armor piece as an item id and never says how heavy
it is ([HEAD,95044,T,16,ARMOR_DIVINES,LEGENDARY,270,...]). UESP's item
database lists every armor item with its armor type in one request (about
60,000 items, 5 MB). The ones of armor type 1, 2 and 3 (light, medium and
heavy) are kept here as three sorted lists of ids. The rest of that export,
jewelry among it, has no weight.

Checked against 48 logs of April to October 2026: all 905 item ids in their
armor slots had a weight in UESP's list. A piece from a set added to
the game after this file was built shows no weight until it is regenerated.

Run after an ESO update that adds gear (needs network access):
    python scripts/generate_armor_weights.py

## Perfected and normal pieces of one set

### family_counts

*[src/player_build.py:472](../src/player_build.py#L472)*

Design: Perfected and normal pieces count together. A trial or
arena set comes in two versions with two set ids, and the game counts
their pieces together towards the set's bonuses: two perfected and
three normal pieces of Slivers of the Null Arca are five pieces of it.
Only the perfected version's own extra line needs its count in
perfected pieces alone.

Measured on 411 split logs (issue #215), over the 15 sets someone wore
in both versions, by whether the wearer was the source of an effect of
the set's in that session:
- five pieces only with both versions counted: 158 of 162 sessions;
- five pieces of one version: 3,537 of 3,594;
- below five with both counted: 1 of 62.
The four without the effect wore Mora Scribe's Thesis (3 of its 6;
one version alone shows it in 19 of 29) and Claw of Yolnahkriin (its
one session; the buff needs a taunt). Minor Slayer, the three-piece
line, was on all 28 PLAYER_INFO lines of the one session that reached
three only together, and on none of the 209 lines below three.

So: set id -> [pieces active on the front bar, on the back bar], as
piece_counts gives them, but a set worn in both versions is one entry,
under the normal version's id, with the two counts added per bar. A set
worn in one version keeps that version's id, so a caller's table has to
list both ids, as SLAYER_SETS and GROUP_SETS do. What needs perfected
pieces alone reads piece_counts. *pairs* is {perfected id: normal id},
the bundled set data's by default (perfected_pairs).

### table_sets_worn

*[src/pen_crit.py:419](../src/pen_crit.py#L419)*

[(set id, its table entry, [pieces on the front bar, on the back])]
for the worn sets the offense table lists, in set id order.

A set's perfected and normal pieces count together towards the lines
the two versions share (player_build.family_counts has the measure). So
when both versions are worn and the table lists both, the lines are
read once, from the normal version's entry, at the two counts added per
bar: two perfected and two normal pieces of Ansuul's Torment give its
four-piece penetration. A perfected version the table lists alone has
only its own extra line there (an arena weapon's two-piece penetration),
which needs its count in perfected pieces, so it keeps them
(tests/unit/test_pen_crit.py holds the table to that shape). *pairs* is
{perfected id: normal id}, the bundled set data's by default.

### set_entries

*[src/gui/fight_render.py:1250](../src/gui/fight_render.py#L1250)*

Design: Perfected and normal pieces on the gear line. The log gives
a perfected set and its normal version two set ids and two names, but
the game counts their pieces together towards the set's bonuses (only
the perfected version's own extra line needs five perfected pieces).
So the gear line shows the pair as one entry, placed by the total:
{'count', 'name'} for a set worn in one version, with 'perfected' (the
perfected pieces among them) and 'perfected_name' added when both are
worn, 'name' then being the normal version's. Entries keep the engine's
order, most pieces first, a pair standing where its total puts it and
ties staying as they came (issue #215).

The entry reads '5x Slivers of the Null Arca (2 perfected)': the total
first, since the first thing asked of a gear line is how much of the
set is there, and it is the shortest of the forms tried, the one that
kept a four-set line on one line of a 560 px pane. The name opens the
normal version's ESO-Hub page and '2 perfected' the perfected one's.

The counts are the engine's, as the line has always had them: every
piece worn, the weapons of both bars among them. So a set with a
weapon on each bar reads one or two above what either bar has active,
which the Build tab's Pcs column gives per bar. Over 411 split logs
that is 88 of the 242 builds wearing a set in both versions and 747 of
the 19,952 wearing one; the line reads five or more where neither bar
has five in 1 and 12 of them (issue #219 asks which count the line
should show).

## Set names

### src/gear_set_database.py

*[src/gear_set_database.py:1](../src/gear_set_database.py#L1)*

Gear set database: set lookups over the generated LibSets data.

The data lives in gear_set_data.py, which scripts/generate_gear_data.py writes
from data/gear_sets/LibSets_SetData.xlsm. Nothing is parsed at runtime.

### scripts/generate_gear_data.py

*[scripts/generate_gear_data.py:1](../scripts/generate_gear_data.py#L1)*

Generate src/gear_set_data.py, the set table the app ships, from the LibSets
addon's workbook (data/gear_sets/LibSets_SetData.xlsm).

Design: the encounter log names a gear piece's set only by its set id
(PLAYER_INFO ... setId). LibSets, the addon the ESO community keeps for
exactly this mapping, publishes a workbook with every set's id, name, type
(crafted, trial, mythic, ...) and item ids; this script reads it at build
time with openpyxl and writes a Python module, so nothing is parsed at run
time and the workbook is not bundled. The CI build runs the script, so a
change here is what ships. Set names are the game's own (issue #79): the
installed client's English string table, committed as
data/client/set_names_en.json by scripts/check_client_names.py, names every
set, and the workbook's spelling differed for 26 of them on Update 51
("Perfect" for "Perfected", "Blood Spawn", three Cyrodiil sets one id out of
place). The workbook gives the set type, the one field the app reads from it
(the five-piece reading in esolog_tail.has_five_piece_bonus, the mythic one
in player_build.is_mythic_set), and the names of the template and "(OLD)"
rows the client lacks. A set the client has and the workbook does not yet is
included under its client name with no type, so it reads as a five-piece,
non-mythic set until the workbook catches up. ESO-Hub links for sets are
looked up by name (see src/ability_icons.py).

### scripts/check_client_names.py

*[scripts/check_client_names.py:1](../scripts/check_client_names.py#L1)*

Compare every name the app bundles by game id with the installed client's own
English text, and keep the committed snapshot of the client's set names.

Design (issue #79): the client's language file, gamedata\lang\en.lang in
depot\eso.mnf, holds the game's name for every set, ability and item, keyed
by id, and it is right on patch day. It holds no structure: not which items
are poisons, not a set's type or bonuses, not an ability's skill line. So the
external sources (the LibSets workbook, UESP, LibFoodDrinkBuff) stay for
structure, and this script checks their names against the client:

  table      Index      what is checked against it
  38727365   set id     src/gear_set_data.py, the set ids named in
                        src/build_issues.py, data/sets/offense.json, and the
                        names data/esohub/sets_en.json is keyed by
  198758357  ability    data/skills/class_passives.json (a mastery's effect
                        by the buff it grants, which is the effect's own
                        name), data/skills/weapon_skill_lines.json, and the
                        skill id lists in src/build_issues.py against their
                        name lists
  242841733  item id    data/items/poisons_en.json (the client writes a tiered
                        poison without its numeral, as the table does)

Item names carry grammar markers ("battle axe^n"); they are cut at the caret
before comparing. The code lists are read with ast, so nothing in src/ is
imported. Food and drink buffs are not checked: data/buffs/food_drink.json
holds ids and kinds only, no names.

Two kinds of finding. A name that differs from the client's, or a name the
client does not have at all, is a difference and makes the run exit 1. An id
the client has no name for is counted, not failed: UESP's tables keep the
rank II to IV ids that skills had before Update 34, which the client no
longer names (432 in weapon_skill_lines.json and 39 in build_issues.py's
skill lists on Update 51), and the LibSets workbook keeps template and
"(OLD)" rows (11). They are harmless in a lookup table, and failing on them
would make the check fail for good. The set lists are stricter: a set id in
build_issues.py or offense.json that the client does not name is a
difference, since every set there was chosen by hand.

Set names are also written to data/client/set_names_en.json with --write-sets.
scripts/generate_gear_data.py takes its set names from that snapshot (CI has
no game client, so the client's names have to be committed) and only the set
type from the LibSets workbook. Refresh it after every ESO update:

```
    python scripts/check_client_names.py --write-sets
```

The run extracts en.lang into a temporary folder with UESP's EsoExtractData
(about 20 s, read-only on the game folder; see scripts/extract_ability_icons.py
for how the extractor and the client are found), or reads an extracted
en.lang.csv given with --lang-csv. Then rerun scripts/generate_gear_data.py,
which reports the sets the snapshot added.

## Set buffs: which set a Major or Minor buff came from

### scripts/generate_set_buffs.py

*[scripts/generate_set_buffs.py:1](../scripts/generate_set_buffs.py#L1)*

Generate data/sets/set_buffs.json: the Major and Minor buffs a set's bonus
grants, by the ability id the encounter log writes for them, so the uptime
line can name the set behind a "Major Slayer" or a "Major Courage" (issue
#79, decision 5).

The log names a buff and never the set it came from, and the game's files
hold no link between the two. UESP's mined skills were the first plan:
findSetBonusSkills.php writes a set's name into minedSkills.setName by
matching the bonus text against ability descriptions. Checked on 2026-10-31
against 395 split logs, that column ties each set to the effect named after
the set ("Pillager's Profit", 184 of 216 sets worn), which the uptime line
already shows under the set's name, and misses the generic buffs: of 58
Major or Minor buffs the logs tie to one set, one was in UESP's table
(Roaring Opportunist got 135920, while its Major Slayer is 93109 and
135923). A generic buff's description never matches a bonus's text.

So this script reads split logs instead. Most sources write a Major or
Minor buff under an id of their own: Roaring Opportunist's Major Slayer is
135923, War Machine's 93442, Master Architect's 93120. Some ids are shared:
the wearers of all three also write 93109 (in 96%, 91% and 91% of their
sessions). Only an id that one set writes can name it. Per log session and player it
takes the sets the player had active (``piece_counts``, a perfected set and
its base counted together, as the game counts them) and every effect id the
player was the source of (EFFECT_CHANGED). A buff id is tied to a set when
all of these hold:

1. Its name ("Major Courage") is in that set's bonus text
   (data/sets/bonuses_en.json), on a bonus whose pieces the player wears.
   This drops the buffs that only ride along with what is worn beside the
   set: Jorvuld's Guidance wearers source Roaring Opportunist's Major Slayer
   in 86% of sessions, because the two are worn together.
2. At least WEARER_SHARE of the sessions wearing the set source it.
3. At most OTHER_SHARE of the sessions wearing no set that names the buff
   source it, so an id that something else writes too is not taken:
   Mender's Ward wearers source Major Vitality 61713 in 95% of sessions, but
   so do 3.8% of everyone else; the set's own 113653 is sourced by no one
   else. Every link that reads right sat at 0.7% or below. Leaving out every
   set that names the buff lets two sets share a buff name with their own
   ids (Spell Power Cure's Major Courage 66902, Olorime's 109994).
4. At least MIN_SESSIONS sessions wear the set.

An id that passes for two sets names neither and is left out (printed, not
written).

It knows only sets someone in the logs wore MIN_SESSIONS times, and reads
the bonus text of the bundled snapshot. Byte-identical copies of one split
(issue #85) are read once. The output holds ids and the game's names only,
nothing about the players.

Run after a patch, or when the logs hold more sets, then review the printed
table before committing the file:
    python scripts/generate_set_buffs.py                    # the app's split folder
    python scripts/generate_set_buffs.py --dir D:/esologs/splits

### sets_behind

*[src/set_text.py:195](../src/set_text.py#L195)*

The sets whose own id of the buff *buff_name* is among *given*, the
set-buff ids a caster had up in a fight; in name order. [] for a row
that is not named after a buff of the table.

Design: The set behind a buff. A group buff from a set is written to the
log twice: once under the buff's own id, the one the uptime strip's row
follows (Major Courage 109966, Major Slayer 93109, Major Force 61747), and
once under an id of the set's own (Spell Power Cure's 66902, Roaring
Opportunist's 135923, Saxhleel Champion's 154830), from the same caster to
the same receivers. In a Dreadsail Reef log both ids of each pair were
gained the same number of times by the same casters on the same receivers
(288, 56 and 122 times). So a row's own intervals cannot say which set a
caster's share came from: they carry the buff's id whatever its source.
What can is the set's own id: the engine notes, per fight, which of the
ids in data/sets/set_buffs.json each player had up on anyone during it
(SetBuffRecorder; the entry's player 'set_buffs'), and a row named after a
buff reads its casters' sets from there (sets_behind). The label is per caster and fight:
a caster who gave the buff from a set and by another means too reads
"from <set>" for their whole share. The table (scripts/generate_set_buffs.py)
knows 34 ids of 24 sets, those someone in the surveyed logs wore, and no id
that several sets write.

### SetBuffRecorder

*[src/set_text.py:70](../src/set_text.py#L70)*

Who had a set's own buff id up on anyone, and when, in raw log
milliseconds: given_in() reads a fight's window out of it, as the buff
timeline's recorder does for the strip's rows.

A fight's casters are those with the id up during the fight, not those
whose GAINED line fell inside it: a buff gained just before the pull
and still up is the wearer's in that fight, as the row shows it, and a
refresh (UPDATED) of a buff this recorder never saw gained counts too.
An interval runs from the first GAINED or UPDATED of an id on a unit to
its FADED, and is credited to every caster seen on it while it was up
(two wearers refresh each other's buff, and FADED is not relied on to
name the caster). The game writes no FADED for a unit that is removed
or dies, and unit ids start afresh in a new zone, so forget_unit and
zone_changed end the open intervals, as effect_rules' tracker does.

## Set text in the hovers, and hover text from the keyboard

### src/set_text.py

*[src/set_text.py:1](../src/set_text.py#L1)*

A set's bonus text, and the set behind a Major or Minor buff (issue #79).

Design: Set text in the hovers. The game's client holds no set bonus text
the app can read (it comes from the server through the add-on API), so the
text is UESP's, bundled per set id in data/sets/bonuses_en.json by
scripts/generate_set_offense.py (CC-BY-SA 2.5, credited in the README and
the About box, and by a short line under each hover that shows it). A set
link's click target stays the set's ESO-Hub page.

What a hover shows is the lines the player has, not the set's whole text:
the lines at or below the pieces active on their better bar. A set's whole
text runs to 573 characters and one five-piece line to 496, and a player
wearing three pieces has no use for the five-piece line. A set worn in both
versions has the lines the two share at the two counts added, as the game
counts them (player_build.family_counts), and the perfected version's own
extra line only at its count in perfected pieces.

Figures are shown at their top value: UESP writes a figure that scales with
level as a range, "Adds 15-657 Critical Chance", low value first, and every
one of the 1,970 ranges in the bundled text reads that way (18 of them
percentages from 0, 12 plain figures from 0; none is a duration or a
distance; tests/unit/test_set_text.py holds the file to it). A player at
the level cap has the high value, so the text reads "Adds 657 Critical
Chance". The bundled file keeps UESP's text as it came.

### set_hovers

*[src/gui/fight_render.py:1348](../src/gui/fight_render.py#L1348)*

Design: A set link's hover. What each set link of one player
carries, by the set's name as the link shows it (a set worn in both
versions has two names, and two links): {'fragment', 'split', 'lines'}.

'lines' are the set's bonus lines the player has (set_text.active_lines):
those at or below the pieces active on their better bar, which the
entry's gear rows carry as the Pcs column shows them (a set worn in both
versions at the two counts added, player_build.family_counts), and its
perfected line at the perfected pieces of that bar, counted from the
rows (piece_counts). With the two bars level, the better bar is the one
with more perfected pieces. An entry without gear rows falls back to
the gear line's own counts. 'split' is '5
pieces: 2 perfected, 3 normal' for a set worn in both versions.

'fragment' goes on the link's address: the pane keeps one hover per
address for the whole fight, and two players can wear one set at
different counts, so the address says which hover is meant, as a
scribed skill's does for its scripts. ESO-Hub ignores it, and the same
address is built for the gear line, the Build tab's gear rows and a
finding's set link, so all three show the same hover (issue #79).

### FightView._show_key_tip

*[src/gui/fight_view.py:325](../src/gui/fight_view.py#L325)*

Design: Hover text from the keyboard. A link's hover text was the
mouse's alone: Qt reports a hovered link (highlighted) and nothing
for one Tab moves to, so a set's bonus lines, an ability's name
behind its icon or a death's cause could not be read without a
pointer. The reader's own Tab or Shift+Tab now shows the text of the
link it lands on, just under the link's line, where the pointer may
be anywhere; a link without text, or leaving the page, takes the
last one away. Not the step keeping_place takes to give a link its
focus back after a redraw: the page redraws on every live fight
update, and the text would come back each time (issue #79).

Qt takes a tooltip down on a mouse press, the wheel or a change of
focus, but not on a key, so text shown for a key would stay over a
page that scrolled or changed under it: it is taken down when the
page is drawn anew, when the reader scrolls and when the focus
leaves (_hide_key_tip).

## Game data against the game's version: the staleness check

### src/data_staleness.py

*[src/data_staleness.py:1](../src/data_staleness.py#L1)*

The bundled game data against the game the log was written by (engine
side, no Qt). Issue #173.

Design: the app ships tables built from the game and from sites that follow
it: set names (the client's language file and the LibSets workbook), set
bonus texts and set buffs, the ESO-Hub link maps, the ability icons, armor
weights, weapon types, poison names, food, class passives and masteries,
weapon skill lines and skill target kinds. After a game update some of it
lags, and until now the app showed the symptoms one at a time, each in its
own place: ``Set#<id>`` for a set the tables do not name, a dash in the
build window's Type column for an item they do not know, a skill's name as
text where its icon would be, a set name with no ESO-Hub link. Nothing said
that the data was behind, so the maintainer learned it from a user.

Two facts make the check cheap. Every logging session's first line names
the game version, ``BEGIN_LOG, time, 15, "NA Megaserver", "en",
"eso.live.12.1"``; and ``data/version.json`` names the version the bundle
was built against, written by ``scripts/stamp_data_version.py`` after a
refresh, with each table's own date. Only the two numbers after the branch
count (12.1): the client's build number never reaches the log, and a PTS
log (another branch) compares by the same numbers. A log written by a newer
version than the bundle's says the data is behind before any symptom shows.

The symptoms are counted where the log first names them, a player's
PLAYER_INFO line: the gear's set ids and item ids, and the abilities on the
two bars with the icons their ABILITY_INFO lines named. Counted, per logging
session (a new BEGIN_LOG starts again):

- a set id the bundled set data does not name;
- an armor or weapon item id the bundled weight or type table does not
  know, for an item at champion level or of a set. A new character's
  starting clothes, the Soul-Shriven Shirt (item 35029) and Sandals (35036),
  are in neither UESP table and were the only unknown items in a year of
  split logs (two logs, 2026-08 and -10): plain low-level items are left out
  so they never read as stale data;
- an ability on a bar whose icon the bundle lacks (icons are looked up by
  the stem of the path the log names);
- a set name with no ESO-Hub page in the link map.

Measured over the 378 distinct split logs of January to October 2026
(four game versions, 11.2 to 12.1), every counter was zero with the data of
1 November 2026, so the status line stays empty in normal play.

Two symptoms are not counted. Food, because no test from the log is
reliable: the 47 listed foods seen use 24 icons of their own
(``crafting_meat_001``, ``plate_of_sugarskulls``,
``disastrously_bloody_mara``), and the family test the food script uses as
a hint (icons starting crafting_, store_, event_ or plate_) flagged a quest
disguise, Q3854 Goblin Disguise, as a food on one of the 2,188 PLAYER_INFO
lines with no listed food, while a new food with an icon like the Bloody
Mara's would pass it unseen. The maintainer's script reports that hint
instead (``scripts/check_data_staleness.py``). And monsters' icons: the bundle
carries the player skills' icons and the ``death_recap_`` family, so 24 of
the 617 killing abilities logged on 12.1 read as text in a death recap by
design, not because the data is old.

The engine sends a check when a session begins and whenever a PLAYER_INFO
line names something new, so a session costs one message when nothing is
found. The check is an immutable value the GUI can keep.

### scripts/stamp_data_version.py

*[scripts/stamp_data_version.py:1](../scripts/stamp_data_version.py#L1)*

Write data/version.json: the game version the bundled data was built
against, the date, and each bundled table's own date (issue #173).

The app compares the version with the one every logging session's BEGIN_LOG
line names, and shows a status line when the log is newer
(src/data_staleness.py); the About dialog lists the dates. Run it as the
last step of a data refresh, once the tables are committed or ready to be:

```
    python scripts/stamp_data_version.py --game-version eso.live.12.1
    python scripts/stamp_data_version.py --log "<a log written by the game now>"
    python scripts/stamp_data_version.py            (the newest split log)
```

Without --game-version the version is read from a log's BEGIN_LOG line:
--log names the file (its last session counts), and with neither the newest
split log in the app's split folder (the setting, or --dir) is read. The
date of each table is its own "generated" stamp; the LibSets workbook,
which has none, gives the date it was last saved. --check exits 1 when a
table's date no longer matches data/version.json, so a refreshed table
whose stamp was forgotten is caught (the unit tests run it).

### scripts/check_data_staleness.py

*[scripts/check_data_staleness.py:1](../scripts/check_data_staleness.py#L1)*

Check the bundled game data against a folder of encounter logs, game
version by game version (issue #173). Run it after a game update, before
the data refresh, to see what the update broke; it changes nothing.

```
    python scripts/check_data_staleness.py                (the app's split folder)
    python scripts/check_data_staleness.py --dir D:/esologs/splits --workers 12
    python scripts/check_data_staleness.py --data-version eso.live.12.0   (what if)
```

Two reports, by the game version each logging session's BEGIN_LOG names:

1. **Coverage**: the set ids, armor and weapon item ids, abilities on
   players' bars, killing abilities and set names the logs name, and how
   many of them the bundle does not know (the app's own rules, from
   src/data_staleness.py: a plain low-level item such as a new character's
   Soul-Shriven clothes is left out, and its count shown apart). It also
   says in how many sessions the app's status line would have spoken, with
   the bundle's version or the one --data-version names, and lists the
   food hint: effects with a food-style icon (the prefixes
   scripts/generate_food_buffs.py uses) on a player with no listed food. The
   app does not count food, since that test is only a hint; monsters'
   icons are listed here for the same reason (the bundle carries the player
   skills' and the death_recap_ icons only).
2. **Fires**: every ability id the app depends on (the default tracked
   effects, the penetration and critical damage rules, the build-issue
   rules' ids and sets, class passives and mastery effects, werewolf,
   companion and Fatecarver ids, the cast kinds' ids) and the companions'
   and boss-flag adds' monster ids, with the sessions of each version it
   appeared in (an effect, a hit, a cast, a PLAYER_INFO line, a unit). An id
   that appeared on the previous version and in none of the newest
   version's sessions is flagged: the game may have renumbered it. A flag on
   an id the previous version saw in few sessions is weak; the share says so.

Logs are told apart by a hash of their first 256 KB, so the copies the old
splitter wrote count once: every file is hashed first and only the largest
copy of each is read, so a truncated split never stands in for its complete
copy. Zipped splits (``*.log.zip``) are read too. The bars are judged with
the slots the engine builds (a Rampage shown as its morph), so the coverage
is the app's own.

## Solo dungeons: the run's Misfortunes

### src/misfortunes.py

*[src/misfortunes.py:1](../src/misfortunes.py#L1)*

The Misfortunes a solo dungeon run was started with (engine side, no Qt).
Issue #70.

The solo dungeons of October 2026 (pen_crit.SOLO_DUNGEON_ZONES: March of
Sacrifices 1592, Moon Hunter Keep 1593) let the player pick Misfortunes at
the door, each one making the run harder. The log writes each picked
Misfortune as a DEBUFF on the player, gained at the door and never faded,
and every PLAYER_INFO line of the run lists its id among the player's
long-term effects (the 2026-10-26 solo Moon Hunter Keep run: six lines, six
hits for each of the three), so the logging player's long_term_effects at
BEGIN_COMBAT, the list the food rule and the passives already read, carry
them at every pull and no new parsing is needed.

Known ids: Warm Welcome 269749, Revoke of Respite 269803 and Alleviating
Assault 269792 from that run; Weary Submission 269799 and Pulled Punches
269804 from the 2026-10-25 solo March of Sacrifices run, which picked those
two and Warm Welcome (each of its PLAYER_INFO lines lists all three). The
texts are the game's own descriptions (the client's en.lang, table
132143172 by ability id), shortened; where the game leaves the figure to a
placeholder, the figure is the hyperioxes.com guide's (Revoke of Respite's
50%), the log's (Alleviating Assault's heals: 5,100 on trash, 8,160 on a
boss) or left out (Weary Submission's). Every ABILITY_INFO icon of these
effects starts with ``debuff_solodungeon_`` (``..._monster_warmwelcome``,
``..._player_pulledpunches``, ``..._player_wearywarriorssubmission``), so a
long-term effect whose icon stem starts with that is named by its logged
name, with no text, until its id goes in the table.

The engine stores them on the fight entry (entry.misfortunes, a list of
[name, text]), in the table's order whatever order the log lists them in
(it differed between pulls of one run): None outside a solo dungeon, so the
fight pane shows nothing there and an entry built before this renders as
before; [] in a solo dungeon run without Misfortunes, which the pane shows
as ``Misfortunes: none``.

## Penetration and critical damage: the spreadsheet from the log

### src/pen_crit.py

*[src/pen_crit.py:1](../src/pen_crit.py#L1)*

Penetration and critical damage: where each player's and the group's come
from, against the caps (issue #37). Engine side, no Qt.

Design. Two stats decide how much of a hit reaches a trial boss: Offensive
Penetration, which cancels the target's resistance (18,200 on the bosses
and mobs of dungeons, trials and arenas, 9,100 overland; a point past the
cap does nothing), and Critical Damage, 50% to begin with and capped at
125% (155% with the Nightblade mastery Above and Beyond). Raid leads check
both with a spreadsheet of checkboxes (LunaCairu's PenCrit Calc, and the
calculators at hyperioxes.com that skinnycheeks.gg recommends): every
source has a fixed value and they add up. This module does the sum from
the log, in two parts.

The player's own part is read from PLAYER_INFO: the passives in the
long-term list by id (Concentration 939 per light piece, Dexterity 2% per
medium piece, Hemorrhage 10%, Piercing Spear 12%, Fated Fortune 12%,
Advanced Species 5% per Animal Companions ability on the bar, Splintered
Secrets 1,240 per Herald of the Tome ability, Dismember 3,271, Feline
Ambush 12%, Hunter's Eye 950, Twin Blade and Blunt 6% per axe and 1,487
per mace, Heavy Weapons 12% for a battle axe and 2,974 for a maul, Blessing
at the Peak 10%, Above and Beyond 25%; every value is the game's own text
on UESP's skill tree, and a lower rank's id carries that rank's value), the
mundus boon with the Divines pieces that scale it (the Lover 2,744 and the
Shadow 11%, each piece of gold Divines adding 9.085%, rounded down as the
spreadsheet rounds), the sets at their worn piece counts
(data/sets/offense.json, generated from UESP's set texts by
scripts/generate_set_offense.py: "Adds 1487 Offensive Penetration",
Velothi's 1,650, Order's Wrath's 8%, Malacath's -50%), a Sharpened weapon,
and the weapon kinds and armor weights from the bundled item tables. A
value that depends on the bar (weapons, slotted abilities, set pieces with
a two-handed weapon) is kept per bar, so a total reads "14,095 / 11,121"
when the bars differ. A conditional bonus (Sul-Xan's 12% after a soul,
Stuhn's 5,312 against Off Balance, Dismember's 3,271 while a Grave Lord
ability is active) is listed with its condition and never added. A set
that gives a buff at all times (Medusa's or Velothi's Minor Force) is
credited with that buff for the whole fight: the game writes neither a
GAINED line nor a PLAYER_INFO entry for a mythic's permanent buff (four
trial logs: Velothi's aura 193447 on 917 PLAYER_INFO rows, Minor Force
61746 on none), so measuring it would read the other Minor Force sources
alone. A set that gives a buff under a condition (Tzogvin's at ten stacks)
is named as a possible source, and the buff measured like any other.

The group's part is what was on the target and on the player during the
fight, valued as Combat Metrics values the same debuffs (its StatDebuffs
table in CombatMetrics.lua): Major Breach 5,948, Minor Breach 2,974,
Crusher 2,108 (1,622 for the gold glyph, times 1.3 Infused, times 1.45
Torug's Pact, read from the caster's weapon), Roar of Alkosh 6,000, Crimson
Oath's Rive 3,541, Runic Sunder 2,200, Crystal Weapon 1,000, Tremorscale
2,640; Minor Brittle 10%, Major Brittle 20%, each Elemental Weakness 5%;
Major Force 20%, Minor Force 10%, Lucent Echoes 11%, Fated Fortune's 7 s
proc 12%. Combat Metrics adds those to the player's stat at every hit and
buckets the damage by the result, then shows the damage-weighted average
with each hit capped, the maximum, and the share of damage dealt over the
cap. The log has every hit with its time and target and every effect's
span on every unit, so the same is done here per second: for each second
and each target hit, the debuffs on that target (a fraction of the second
counts as that fraction) and the buffs on the player, times the damage
dealt that second, kept as a histogram of (penetration value, status
effects on the target, damage), so a reader can add any static part and
any cap and get the capped average (the effective figure) and the share
over the cap. In a fight with a boss only the bosses are measured; in a
trash fight every hostile hit.

Not in the log, and the reason the renderer adds "assumed" rows from the
Settings rather than this module: the Champion Point stars that only change
a stat. Four trial logs (2,292 PLAYER_INFO rows) never list Piercing (700
penetration), Fighting Finesse (8%), Deadly Aim or Master-at-Arms, and show
Backstabber (10% while flanking) only as 35 self-applied GAINED lines;
stars that are effects (Exploiter, Bulwark, Reaving Blows) are listed, so
the game simply has no effect for a stat star. Force of Nature (660
penetration per unique status effect on the target in Combat Metrics'
table, the star it calls wrathCP) is the same, but the status effects on
the target are logged (9,522 GAINED lines in one Sunspire log), so when the
reader assumes the star its value is the measured count of effects times
660. The Settings toggles only change the rendering, so a change needs no
engine restart and a fight entry holds nothing but what the log said.

What else the survey showed: Divines is the trait on 13,620 armor pieces
and no weapon of 2,292 builds is Sharpened; every Crusher glyph (302
weapons) is gold at CP 160; Fated Fortune's proc fired 2,374 times, so its
real uptime is measured, not assumed; the trial dummy applies the trial's
own debuffs to itself (Crusher 120007, Alkosh 120018, Breach 120010 and
120019, Minor Brittle, Elemental Catalyst), which is how a parse at a
dummy is known to be against 18,200 resistance in a house zone whose
difficulty reads NONE. It applies them once, as it spawns, and keeps them,
so a session begun after the spawn has no line for them and the log alone
would read the player's own penetration against an overland cap; a fight
against a unit named "Target Iron Atronach, Trial" therefore credits them
for the whole fight (TRIAL_DUMMY_DEBUFFS), as Combat Metrics reads them
from the game at the pull. Checked against a Combat Metrics report of a
25 s parse (2026-10-24): own penetration 3,126 (one light piece, Aerie's
Cry's two pieces, Piercing) plus the dummy's 17,030 is its maximum of
20,156 exactly, damage and dps agreed within 0.5%, and the ability table
row for row.

Solo dungeons and the Armour row (issue #55). The solo dungeons of October
2026 are the group dungeons' layouts and bosses at a zone id of their own,
with the dungeon's name and difficulty NONE on the ZONE_CHANGED line (the
solo March of Sacrifices is zone 1592, the group dungeon 1055, logged on
2026-10-25 and 2026-09-22; the solo Moon Hunter Keep is 1593, the group
dungeon 1052, logged on 2026-10-26 and 2026-06-11); nothing else in the log
says solo. The Misfortunes picked at the door were absent from the March of
Sacrifices log and present in the Moon Hunter Keep one: each is a DEBUFF the
player carries from the door to the end (Warm Welcome 269749, Revoke of
Respite 269803, Alleviating Assault 269792), every enemy spawns with a
"Misfortune Level Three" BUFF (267457 and 267460 on trash, 272449 and 272450
on the boss), and Alleviating Assault works as a HEAL event from the player
to the enemy hit, 5,100 on trash and 8,160 on a boss at most every 3 s, so
the player's heal events include heals on hostile units. None of the three
touches armour (double enemy damage, half the healing received, the heal),
so the figures here hold under any Misfortune; the boss's logged health,
2,157,795 for Jailer Melitus, is the guide's figure for three Misfortunes,
which is why the guide's armour figures are trusted. The solo bosses have
monster ids of their own (Jailer Melitus 132991, where the group dungeon's
bosses are 83219 to 83223), so a per-boss table could not reuse the group
ids. Read by difficulty alone a solo dungeon is overland, 9,100, so
SOLO_DUNGEON_ZONES names the ids and zone_kind reads it first; the figures
are the hyperioxes.com Moon Hunter Keep guide's: trash 18,200 like any
instance, bosses 27,300, the final boss 36,400, and the game's cap of 25,000
on an enemy's armour, above which penetration changes nothing until the
debuffs bring the armour under. Every boss is taken at 27,300 (the
maintainer's choice, 2026-10-26); the labels say the final boss has more.
The buff timeline's Armour row (armour_row) draws the target's armour less
the group's armour debuffs on it, second by second, from a series
fight_fields keeps on the target the group damaged most: spans of equal
debuff sum and names, the sum rather than the remainder so the Settings' cap
override can restate the estimate. The remainder is averaged over time for
the label, where the build window's effective figures weigh each second by
the damage dealt; the two are different questions (how long the armour was
down, and how much of the damage met it down).

The row's window (issue #64). A fight runs from BEGIN_COMBAT to
END_COMBAT, and the target the row follows need not be there for all of
it: the combat that ends at Xoryn starts at the Defense Prisms and runs
through Baron Rize and the gauntlet, and over 33 Lucent Citadel logs
Xoryn was added a median 435 s into a median 549 s fight; Nahviintaas
lands as a new unit id each time and is hit for about 20 s per landing;
a trash pack's mob lives for a third of its fight. Drawn over the whole
fight the row stood full for the time before the boss, the label read
14,500 to 16,000 left on Xoryn pulls and the click said 77 to 83% without
a debuff, when over the time the group was hitting him it was 2,565 to
5,978 and 0 to 1%. So the row is measured over the seconds the group
damaged its target (the hits the engine buckets per target per second,
_armour_window), a gap of up to ARMOUR_GAP_S seconds between hits bridged
and a longer one left blank (a dragon in the air), and nothing is drawn
before the first hit or after the last; the label's average, the lowest
point and the no-debuff share are over the drawn time, the click summary
names the window, and the damage-weighted figure (weighted_pen) sits
beside it so the row and the build window can be seen to agree. A boss in
several unit ids shares the row: every boss-flagged unit of the row
target's name, each second read on the one hit hardest that second
(_armour_series). Among a pack's equal-damage mobs (each takes its
health) the row follows the one hit over the longest window, then the
first hit (_row_target), where the largest unit id, the last spawned, was
taken before. The boss-scoped uptime rows above it still measure over the
whole fight (issue #64 lists that choice). The engine's boss_window was no
window for the row while the Prisms and the Baron carried the game's boss
flag into the fight's bosses; since issue #67 they are adds (boss_units),
so the row's target on a Xoryn pull is Xoryn alone either way.

The pack reading (issue #66). Windowed to its target, the row left the
first seven minutes of a Xoryn pull blank, where the group hit 245 to 279
units and the armour debuffs on them mattered as much, and on a trash
fight it followed one mob of a pack of twenty. The question the row could
not answer was what armour the group's damage was going into, second by
second, whatever it was hitting. So fight_fields now keeps the armour
debuffs' coverage on every hostile the group hit, not only the bosses (the
crit debuffs, the status effects, the debuff rows and the histograms stay
the targets'), and _pack_series reads each second on the hostile hit
hardest that second, ties to a boss among them, then to the unit read the
second before so a pack of equals does not flicker, then to the lowest
unit id; a gap of up to ARMOUR_GAP_S seconds carries the last unit's
reading, as the boss row bridges its own, except across the boss row's
own time. In a boss fight the reading
fills the row outside the boss's window, drawn paler so the two are told
apart, the hover naming the unit of the moment and the label keeping the
boss's figure (the pack reading is lower, since adds carry fewer debuffs
for less time, and a second spent on an add while the boss stands
debuffed reads on the add: a different question, not a better answer to
the boss's); in a fight without a boss it is the row, and the label is its
average. The estimate is held at one value per row (a solo dungeon's boss
at 27,300 against its trash at 18,200 would otherwise change the bar's
scale mid-row), and an interval read on a unit whose armour differs
carries that figure for the hover. From the #64 replays: a Xoryn pull
read this way averages 3,200 to 6,200 left with 7 to 15% of the damaged
seconds undebuffed over 130 to 210 switches of unit, Xoryn himself the
hardest-hit unit in 19 to 25% of them; a trash fight 2,700 to 10,400 left
where the one-mob row read 10,317 to 16,800; a clean boss fight's pack
seconds are few and read lower than the boss (Count Ryelaz 1,053 against
6,348).

### scripts/generate_set_offense.py

*[scripts/generate_set_offense.py:1](../scripts/generate_set_offense.py#L1)*

Generate data/sets/offense.json: what each gear set does for penetration and
critical damage, by the set id the encounter log writes, for the build
window's Penetration and Critical damage sections (pen_crit.py, issue #37).

The log gives an equipped item's set id and nothing about the set's bonuses.
UESP's set summary lists every set with its bonus texts, one request (714
sets, 0.8 MB); the texts are the game's own. This script keeps, per set and
per piece count, the lines that matter here:

- a flat Offensive Penetration line ("(2 items) Adds 34-1487 Offensive
  Penetration": the second figure is the value at CP 160), kept as 'pen';
- a flat Critical Damage line ("(5 items) Increases your Critical Damage and
  Critical Healing by 8%"), kept as 'crit' (Malacath's "decreases ... by 50%"
  as -50); a sentence after it that doubles or adds to the bonus under a
  condition is kept as 'note';
- a buff the wearer always has ("Gain Minor Force at all times", Oakensoul's
  list), kept under 'gives': the game writes no GAINED line and no PLAYER_INFO
  entry for such a buff (four trial logs: Velothi's aura 193447 is listed on
  917 rows, Minor Force 61746 on none), so the wearer is credited with it for
  the whole fight; a buff the wearer gets under a condition ("After dealing
  direct damage, you gain Minor Force", Tzogvin's at ten stacks) is kept
  under 'gives_when' with the text as 'when', named but measured from the
  log like any other buff;
- a conditional bonus to the wearer ("When you deal damage to an enemy who is
  Off Balance, your Offensive Penetration is increased by 123-5312 for 10
  seconds"), kept as 'pen_up_to' or 'crit_up_to' with the text as 'when',
  shown but never added to a total;
- a debuff or group buff the set puts on others (Roar of Alkosh, Crimson
  Oath's Rive and Tremorscale reducing Armor or Resistance, Night Mother's
  Gaze's Major Breach, Nunatak's Major Brittle, Elemental Catalyst's
  weaknesses, Lucent Echoes, Saxhleel Champion's Major Force), kept under
  'provides' so a group row can name the wearer's set as its source.

Of the 714 sets on the Update 51 export, 65 carry a flat 1487 line, seven
arena weapons 1190, Spriggan's Thorns and Spinner's Garments 3460; 72 sets
mention Offensive Penetration and 52 Critical Damage in some form. The
texts are classified by sentence: a first sentence that is nothing but
"Adds N Offensive Penetration" or "Increases your Critical Damage ... by N%"
is flat; a sentence that opens with a condition (When, While, After,
Whenever, Dealing, Touching, On, If, Each, Every) is conditional. A set the
export does not describe, or a bonus worded in a way this script does not
read, is simply absent: the section then shows nothing for it.

The same reply also gives data/sets/bonuses_en.json (issue #79): every set's
bonus lines as the game words them, by set id, for a set's description in the
app. The game's client files do not hold this text (the client assembles a
set's tooltip from server data at run time), so UESP's copy, which its
uespLog addon reads from the game, is the source; it is bundled so nothing
is asked of UESP at run time, and it carries UESP's CC-BY-SA 2.5 attribution
like this file. Each line keeps its piece count, whether it is a perfected
bonus ("(2 perfected items)"), and its text with runs of spaces closed up;
the figures stay as written ("Adds 15-657 Critical Chance": the second value
is the one at Champion Point 160). Set names in it are UESP's; the app names
a set from its own table by id.

Run after an ESO update that adds or changes sets (one request to UESP; UESP
asks heavy users to go lightly, so do not loop it):
    python scripts/generate_set_offense.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_set_offense.py --from build/esobuild-assets/sources/set_summary.json

### _pen_crit_html

*[src/gui/build_render.py:722](../src/gui/build_render.py#L722)*

The Penetration and Critical damage sections (pen_crit): the player's
own rows and the assumed Champion Point rows, the fight's debuffs on
the boss (uptime, value, casters) and the buffs on the player, then the
totals: own, with every debuff at full uptime, and effective (each
second of the player's damage capped, as Combat Metrics caps each
hit), against the cap. The effective line is the conclusion, so it
sits in a framed row of its own with a 3 px bar at its left edge
(issue #143): a box rather than an underline, because the app's one
underline is the hover cue on a clickable name or figure; a table
cell rather than a <p>, because Qt rich text draws borders on cells
only; the frame is the build card's hairline, and the bar in the muted
colour gives the cue the contrast a hairline lacks (about 6:1 against
the page in either theme), so it is seen without colour vision. The
muted 'no damage measured' line stays in the plain row: a frame round
an absence would draw the eye to nothing.

## Section headings: the one element Qt rich text draws a rule on

### _heading_html

*[src/gui/build_render.py:554](../src/gui/build_render.py#L554)*

A section heading with its rule, as a one-cell table head: Qt rich
text draws borders on table cells and never on a <p>, so the Damage
dealt and Resources headings, <p> elements with a border-bottom until
issue #143, had no rule while the gear grid and the Penetration and
Critical damage heads (the same form inside their tables) had one; the
damage taken window's section titles (taken_render) take this form too.
*extra* follows the title (a link, a caption); the anchor, when there
is one, goes first, where scrollToAnchor finds it: Qt hangs an empty
named anchor on the next text it lays out, the heading cell.

## Possible build issues: what the log proves about a build

### src/build_issues.py

*[src/build_issues.py:1](../src/build_issues.py#L1)*

Possible build issues: what a player's logged build and their fights say
about likely mistakes, shown behind an (i) on their row of the fight pane
and repeated in the build window (engine side, no Qt). Issue #16.

Design: a finding is something the log proves about the build the player
pulled with, and every finding carries the rule it comes from in plain
words, so the reader learns the rule from the finding. The rules are the
maintainer's (decided 2026-10-24), checked against 83 split logs of
September and October 2026 (1,615 fights, 13,998 player-fights, 393
characters); with them, 17% of the characters seen would carry a note. Per
rule, player-fights / distinct characters in that survey:

- **Nirnhoned on an off-hand weapon** (429 / 17, every one a DPS; the
  classic form is a Precise main hand beside a Nirnhoned off hand). The
  trait raises the damage of the weapon it is on, and UESP's Dual Wield
  page gives Dual Wield Expert as Weapon and Spell Damage equal to 6% of
  the off-hand weapon's damage, so an off-hand Nirnhoned is worth about a
  sixteenth of a main-hand one. A shield's Nirnhoned (ARMOR_NIRNHONED, 4
  tank fights) is the armor trait and is not reported.
- **The same glyph on both weapons of a bar** (421 / 22: Absorb Stamina,
  Berserker, Poisoned, Weakening, Absorb Health), whatever the glyph.
  Identical glyphs share one cooldown: measured on every dual-wield front
  bar of those logs, the same glyph from one player never fired twice
  within 4.0 s whether the bar carried it once or twice, and the proc rate
  was the same (Absorb Stamina 6.0 against 6.5 per minute, Poisoned 6.2
  against 7.2, Berserker 9 s gaps either way), so the second glyph never
  fires. The same glyph on both bars (112 / 7: a tank's Hardening or
  Crusher on both bars, Berserker on both bars of a DPS) is not reported:
  with a cooldown twice the buff's duration, a copy on the other bar fills
  the gap after a swap.
- **Two or more heavy armor pieces on a damage dealer** (218 / 9; five or
  more 103 / 4). Heavy Armor's passives add nothing to damage. One heavy
  piece is the usual Undaunted Mettle split (618 of 8,766 DPS
  player-fights) and is not reported. The role is the app's heuristic
  (infer_player_role), which reads the dominant resource, so a
  health-stacked DPS reads as a tank and a stamina-heavy fake tank as a
  DPS: 363 "tank" player-fights wore no heavy at all. The rule therefore
  asks for the DPS role and that the player has not taunted this session.
- **A weapon skill on a bar holding another weapon** (235 / 14 with the
  bar in use; Stampede left on a staff back bar is the commonest). The
  skill's line comes from the bundled weapon_skill_lines.json (UESP's
  player skill table, scripts/generate_weapon_skill_lines.py), or from the
  grimoire a scribed skill's icon names; the bar's line from the weapon
  types of its two slots. The back bar under Oakensoul Ring (set 658; 55
  more player-fights) is skipped, since the ring forbids swapping, and a
  bar whose weapon the bundled table does not know is not judged.
- **Elemental Drain** (124 / 5: tanks 69, healers 50, DPS 5, all in
  trials), per player, the maintainer's decision. The finding states both
  morphs: Drain (ids 39095, 41559, 41563, 41567) applies Major Breach and
  Minor Magickasteal; Elemental Susceptibility applies Major Breach and
  the Burning, Chilled and Concussion status effects every 7.5 seconds.
- **A proc set that never fires** (Roar of Alkosh 12 / 3 and Roaring
  Opportunist 19 / 8 at the 60 s floor). Judged per logging session, not
  per fight: in fights of 90 s or more Alkosh fired for 112 of 117
  wearer-fights, yet 30 of 219 wearer-fights under 30 s had no proc though
  the set worked. So the tracker counts, per player and set, the fights of
  a minute or more the set was worn in, and whether the set's effect was
  ever sourced by the player in any fight of the session; one fire clears
  the finding for the session. In those logs Alkosh wearers sourced Roar
  of Alkosh as 76667 and 75751, Roaring Opportunist wearers Major Slayer as
  93109 and 135923. Only 135923 counts: War Machine and Master Architect
  wearers write 93109 too (48 of 53 and 76 of 84 sessions without Roaring
  Opportunist, 395 split logs of 2026-10-31), so either would hide a
  Roaring Opportunist that never fires, while in Roaring Opportunist
  sessions the two ids came together (both in 152 of 159, neither in the
  other 7). The other Major Slayer ids, 93120, 93442 and 177886, come from
  other sets. The one wearer who never fired Alkosh never used a
  synergy through a whole Halls of Fabrication run, 240 s fight included.
- **Huntsman's Warmask that never fires** (issue #47, the same session
  rule, the mythic's one piece being the set): its Mark of Hircine
  (252048, GAINED with the wearer as source) is placed by a bash or a fully
  charged heavy attack, and a wearer who places none has a mythic doing
  nothing. The issue was filed the other way round, as a flag on a wearer
  who bashes (a bash can move the mark from the boss to an add, where it
  halves the wearer's damage to everything else for up to a minute), and
  the survey over the same 91 logs of September and October 2026 decided
  it: 29 of the 30 wearers bash, in 96% of their fights of a minute or
  more (393 of 515 wearer-fights had a damaging bash, a median 3 a fight),
  1,292 of the 1,401 marks followed a bash and 55 a heavy attack, and in
  132 of 396 boss wearer-fights (18 of 29 wearers) the mark sat on a unit
  that is not a boss for a median 11% of the fight. Half of those units
  were Sunspire's Eternal Servants and Kyne's Aegis's Lieutenant Njordal,
  which a group kills on purpose, so a flag on bashing would have been a
  permanent note on every wearer and a wrong verdict a third of the time;
  the maintainer chose the inverse on 2026-10-26, and the mark, which a
  heavy attack places too, is the fact the log carries (his own Aetherian
  Archive session marked by heavy attacks alone). In those logs no
  wearer-session with a fight of a minute or more was without a mark, so
  the rule is quiet until a wearer who never triggers the set turns up.
- **A group buff set complete on one bar only** (80 / 3), for Pearlescent
  Ward, Xoryn's Masterpiece and Lucent Echoes, whose five-piece bonus is a
  buff for the whole group that holds only while five pieces are active.
  The rule cannot be general: 38% of all five-piece wearings in the survey
  were one-bar, which is normal for proc sets and front-bar damage sets.
  Piece counts per bar come from player_build.family_counts (a two-hander
  counts as two, and a set's perfected and normal pieces count together,
  as they do in the Minor Slayer and proc-set checks). A build without a
  back-bar weapon, or wearing Oakensoul Ring, is not reported.
- **A tank with no taunt or pull** (95 / 3 with the gates below; added the
  same day at the maintainer's request). The health pool alone is not a
  tank: of 3,154 health-dominant player-fights in the same logs, 762 had
  neither a taunt nor a pull on their bars and never taunted, but 519 of
  those wore at most one heavy piece and were damage dealers or healers
  whose health happened to be their largest pool, and 40 more taunted
  through the Tormentor set's charges and chains. Real tanks (a taunt
  slotted and taunting) dealt a median 0.10 of an equal share of the
  group's damage, 0.22 at the 90th percentile and 0.27 at the 95th. So
  besides the role, the bars and the session's taunts the rule asks for
  tank gear (a shield, an ice staff or five heavy pieces), at most half an
  equal share of the damage, and no healer sign (a restoration staff on a
  bar, or more healing to others than damage dealt: a heavy-armor healer in
  Sunspire would otherwise be flagged). Taunt and pull ids are UESP's for
  every rank plus the ids the bars carried in the logs; names count too,
  since the game now calls the chains Chains of Flame, Dominance and
  Devastation and the Arcanist's rank ids differ from UESP's. A scribed
  skill taunts or pulls by its focus script, Taunt or Pull, which names it
  Goading or Leashing. Destructive Clench taunts only with an ice staff in
  hand, when it is cast as Frost Clench.
- **No food or drink at combat start** (issue #54; 535 player-fights, 3.6%,
  and 39 named characters in 91 split logs of September and October 2026
  with 1,681 fights and 14,895 player-fights, the maintainer's own character
  the most frequent case, in casual content). The long-term effects the
  PLAYER_INFO line lists are matched against the bundled LibFoodDrinkBuff
  table (player_build.food_buff, data/buffs/food_drink.json, 92 ids), the
  way the build window's Food line is; a player with no match fought
  without a consumable's maximum stats or recovery. The check is by id, not
  icon: the foods in those logs carried 18 different icon stems
  (crafting_cooking_, crafting_meat_, plate_of_sugarskulls, event_jester_,
  store_magickafood_, crafting_poisonmaking_reagent_troll_fat...), unlike
  mundus boons, so a consumable newer than the table reads as none, which
  the finding says. No player without a match carried an effect with a
  consumable-looking icon, so the gap was a missing meal every time. A meal
  eaten during the fight is noted with its time. A player whose food was
  listed at combat start and faded during the fight, with nothing eaten
  before the end, gets the second form, "{food} ran out 2m10 into the
  fight" (13 player-fights in those logs): the engine keeps each player's
  food ids as combat starts and follows their GAINED and FADED lines
  (CombatEncounter.note_food), and a drink logged as several effects
  (Witchmother's Potent Brew) is only out when all of them have faded.
  Judged per fight with no floor: the fact is about combat start, and the
  cue clears once the player eats. Not judged when the table cannot be
  loaded (the player dict then has no 'food' key).
- **No Minor Slayer in a veteran trial group** (issue #62; 787 of 10,572
  veteran DPS player-fights, 7%, and 29 of 225 characters, in the 84 newest
  trial split logs of May to October 2026 with 1,581 fights and 18,684
  player-fights). Minor Slayer is 5% more damage to dungeon, trial and
  arena monsters. Every trial's sets grant it at three pieces and Oakensoul
  Ring grants it outright: SLAYER_SETS holds the
  38 three-piece sets by game set id, from UESP's set summary (the
  esobuild asset export's set_summary.json, its gameId field), and the ring
  is OAKENSOUL_SET_ID. The maintainer's scope (2026-10-26): damage dealers
  only, since healers carried a source in 47% of their player-fights and
  tanks in 13%; large groups only (five or more players,
  effect_rules.group_size_class, the class the uptime line's "expected
  large" reads); veteran difficulty only, since in the 113 normal-difficulty
  fights 46% of the DPS lacked one; and a listed set at three pieces on
  one bar is enough (1% of DPS player-fights: a body piece of Relequen with
  a back-bar staff). With the heavy-armor rule's never-taunted guard, for
  the same reason. Judged from the gear, not the effect: the set bonus is
  ability 147226 in the PLAYER_INFO effects (listed for 10,935 of the
  10,936 wearers with three pieces on both bars), but the ring's is not
  (1,110 of 1,349 ring wearers listed no 147226; the 45596 "Slayer" they
  carry is the Fighters Guild passive). A PLAYER_INFO with an empty gear
  list (130 player-fights, 58 of them listing 147226: the empty-equipped-set
  trap of issue #49) is not judged. Per fight, no floor: the gear at combat
  start is the fact, and a changed build clears it next fight. The builds
  without were Deadly Strike with Tide-Born Wildstalker or Spattering
  Disjunction, Azureblight Reaper with Corpseburster, Savage Werewolf with
  Order's Wrath. The finding is one sentence (issue #127 trimmed it): it
  once named the complete sets worn instead, which read as noise.
- **A second copy of a group buff set that gave the group next to nothing**
  (issue #172; 21 copies, by player and set, in 17 of the 378 unique split
  logs of 12 January to 1 November 2026, on 80 fights; a count of 379 seen
  once took in a split the app was still writing). The issue proposed each wearer's
  loss: the group's uptime of the set's buff less the same without that
  wearer's spans. The log does not support the reading the issue gave it.
  The game writes one instance of a set's buff per receiver, credited to
  one wearer at a time: in five fights with two full wearers of Pearlescent
  Ward, Lucent Echoes, Spell Power Cure, Master Architect or Powerful
  Assault, no second wearer's GAINED arrived while the first wearer's
  instance was on that receiver (0 of 6,259 lines; over the corpus, 3,797
  of 3.78 million for the three whole-group sets, 0.1%, at handovers). Two
  wearers split the group between them (two Wards, six players each, in a
  Lucent Citadel fight), so what a wearer is credited with is not what the
  group would lose without them. Nor does one wearer of a whole-group set
  reach everyone: with one wearer, living players had Pearlescent Ward a
  median 89.6% of their living time in groups of 9 to 12 (698 fights),
  Lucent Echoes 88.7% (737), Xoryn's Masterpiece 87.3% (341), and within
  the same sessions a second Ward added 9 points (two sessions), a second
  Echoes a median 6 (four), when the group spread. What the crediting does
  prove is an upper bound: a receiver's buff is one wearer's at a time, so a
  wearer credited with almost none of the other players' time added almost
  nothing. The rule reads each full wearer's credited share of the other
  group members' time, each for the part of the fight they were there (for
  Lucent Echoes the members not wearing it, since its wearers never
  benefit); a player of the zone outside the group is no receiver, or a
  city or Cyrodiil would dilute the share to nothing. A set's buff ids are
  joined per receiver first, so two of its buffs on a player at once
  (Magma Incarnate's Minor Courage and Minor Resolve) count the time once.
  It flags a wearer whose share stayed under
  SECOND_SOURCE_SHARE (2%) in every fight of a minute or more of the
  session that another full wearer was in, provided another wearer's copy
  reached the group in at least one of them: two Master Architects in a
  fight with no ultimate cast both read 0.0, and neither is a second copy
  beside a working one. In those logs' fights of a minute or more with two
  or more full wearers, the lesser copy's share is a median 22% for Spell
  Power Cure, 21% for Lucent Echoes, 28% for Pearlescent Ward, 11% for
  Master Architect, 8% for Saxhleel Champion and 6% for Powerful Assault,
  Roaring Opportunist and Ozezan the Inferno. The rule finds Saxhleel
  Champion and Powerful Assault five times each, Spell Power Cure and Lucent
  Echoes three, Ozezan the Inferno twice, Master Architect, Roaring
  Opportunist and Xoryn's Masterpiece once, and Pearlescent Ward never; one
  is an Echoes and Powerful Assault wearer whose copies reached no one in
  17 Dreadsail Reef fights. A survey that read each player's last
  PLAYER_INFO line found more, among them members who had left or changed
  sets (a Ward "wearer" in four Cloudrest fights who no longer wore it); the
  engine judges each fight's own build. The sets judged are those
  whose value is the buff they give others (GROUP_BUFF_SETS); a set whose
  buff is its wearer's own (Kinras's Wrath, Huntsman's Warmask) or a
  debuff on enemies is never judged, though data/sets/set_buffs.json lists
  it, since a second copy of a damage set stacks. The buff's spans are kept
  per wearer and receiver (GroupBuffCredit), not taken from the uptime
  rules, which the reader can edit away.
- **A second Enlivening Overflow or From the Brink slotted** (issue #172).
  A player who slots either Champion Point star lists it in the PLAYER_INFO
  long-term effects (156008, 156017), and its procs name the holder as
  source: Enlivening Overflow writes 156012, the 6 s buff on the healed
  player, and 156011, a hidden effect of 12.0 s (231,505 of 250,241 lasted
  11 to 13 s, the rest ended with a death); From the Brink 156020, the
  shield (its value in the target's shield field), and 156019, hidden, 30.0
  s (2,707 of 4,573). The hidden effect is the per-target cooldown, and every
  holder shares it: of 282,366 Enlivening Overflow procs, 2 landed on a
  player while another holder's stood on them (105 while the same
  holder's did); of 4,572 From the Brink procs, none. Holders take turns.
  With one holder the 6 s buff covered a median 32% of a 12-player group's
  time (578 boss fights), with two 36% (295): a second adds about four
  points against a ceiling of 50%. So the rule counts each holder's procs
  over the session's fights of a minute or more that had two or more
  holders: an Enlivening Overflow holder whose procs stayed under
  STAR_EVEN_SHARE (30%) of an even share of them (15% of the procs with
  two holders, 10% with three; seven holders sharing evenly are never
  flagged, where a fixed 15% would flag all of them) is flagged, and a From
  the Brink holder who never procced while another did (the star needs a
  heal on a player under 25% health, which a damage dealer who slots it
  rarely gives). Either is judged only once the other holders have procced
  STAR_MIN_OTHER_PROCS (5) times in the fights counted: of the 10 From the
  Brink holders still at no proc when their session ended, five sat beside
  a holder with one or two procs, which two equal holders leave half the
  time. The procs are counted per fight (CombatEncounter.note_star_proc)
  from the fight's BEGIN_COMBAT: the zone's first encounter is made before
  the pull and reused, and the procs while the group buffed up are not
  the fight's. A player key that names a unit only until the zone changes
  ('unit:<id>') is retired then (BuildIssueTracker.retire_players), so a
  new player on that unit id inherits none of these records.

The lists a later rules text could lift out (the maintainer's separate
issue) are module data: GROUP_SETS, GROUP_BUFF_SETS, PROC_SETS, SLAYER_SETS,
STARS, ELEMENTAL_DRAIN_IDS, OAKENSOUL_SET_ID, the taunt and pull tables,
the weapon lines table. The checks themselves are code.

### BuildIssueTracker

*[src/build_issues.py:1117](../src/build_issues.py#L1117)*

The rules judged over a logging session rather than a fight: the
proc sets that never fire, a second copy of a group buff set or a
second holder of a Champion Point star that added next to nothing
(issue #172), and who has taunted (the heavy-armor rule's guard). Keyed
by the engine's per-session player key; a fight is keyed by its start,
so a fight the game cut in two and republished replaces its own record
instead of counting twice. reset() at BEGIN_LOG.

### GroupBuffCredit

*[src/build_issues.py:841](../src/build_issues.py#L841)*

Whose copy of a group buff set's buff each player had, over time
(issue #172): the spans of GROUP_BUFF_EFFECT_IDS per (effect, source,
target) unit, in raw log milliseconds.

The game writes one instance of such a buff per receiver, credited to
one wearer at a time (see the module notes), so a span is that wearer's
credit for that player. GAINED or UPDATED opens a span when none is
open (a refresh after a missed GAINED), FADED closes it, and a span
that resumes within MERGE_GAP_MS of its last close is the same span
(Pearlescent Ward is written as a FADED and a GAINED every second). A
zone change ends the open spans (zone_changed: unit ids are handed out
afresh), so does a unit's removal for its own (forget_unit), BEGIN_LOG
drops everything (reset), and spans that ended before a published fight
are pruned (prune_before), as the uptime rules' are.

### scripts/generate_weapon_skill_lines.py

*[scripts/generate_weapon_skill_lines.py:1](../scripts/generate_weapon_skill_lines.py#L1)*

Generate data/skills/weapon_skill_lines.json: every active skill of the six
weapon skill lines (Two Handed, One Hand and Shield, Dual Wield, Bow,
Destruction Staff, Restoration Staff) by game ability id, with its line and
name, for the build-issue rule that spots a weapon skill slotted on a bar
holding another weapon (build_issues.py).

The encounter log lists a bar's skills by ability id and never says which
skill line a skill belongs to. UESP's player skill table does: one request
(about 4,400 rows, 2 MB) lists every player skill with its line, rank and
whether it is a passive. The rows kept here are the non-passive rows of
the six lines with a rank of 1 or more: every rank of every morph (the log
writes the id of the rank the player has: Stampede is 38788, 39797, 39802
or 39807), the scribed grimoire skills of those lines included (Elemental
Explosion is logged as 217228 and a dozen other ids, one per focus script).
Left out: the passives (never in a bar), the rank -1 rows, which are
internal effects such as Bash and Follow Up, and UESP's own rank ids for
crafted skills (20217228 for rank 2 of 217228), which no log ever carries.
605 ids on the Update 51 client.

Run after an ESO update that adds a weapon skill or a grimoire (one request
to UESP, which asks heavy users to go lightly, so do not loop it):
    python scripts/generate_weapon_skill_lines.py
or from a reply already on disk, such as the one the esobuild export keeps:
    python scripts/generate_weapon_skill_lines.py --from build/esobuild-assets/sources/player_skills.json

## Tracked effects: the uptime line as rules anyone can paste

### src/effect_rules.py

*[src/effect_rules.py:1](../src/effect_rules.py#L1)*

Tracked effects: rules anyone can paste, and the tracker they drive
(engine side, no Qt). Issue #10.

Design: every item on the uptime line is a rule. A rule names an effect by
its ability ids and asks for its uptime or its stack count on a chosen kind
of unit, in a plain text anyone can copy to others. One rule per line::

```
    # Name = ability ids... on <scope> [stacks | each | dots] [expected <sizes>]
    Major Courage = 109966 on group expected large
    Taunt         = 38254 on boss each expected small large
    Off-Balance   = 45902 62988 39077 34733 20806 130139 on boss
    Touch of Z'en = 126597 on boss dots
    Crux          = 184220 on self stacks
```

A rule matches any of its ids (an effect such as Off-Balance has one id
per skill that applies it). The scope says whose effects count: ``self``
is the player who writes the log, ``group`` any group member, ``pets`` a
group member's pet, ``boss`` an enemy the game flags as a boss, ``enemies``
any hostile. Three measurements: ``uptime`` (the default) is the share of
the fight the effect was on at least one unit in scope, the question "was
it up?"; ``stacks`` is the mean stack count while it was up, with the peak,
for effects that stack (Crux, Touch of Z'en, Arms of Relequen); ``each``
measures the effect on every unit of the scope separately, over the time
that unit was alive in the fight, and shows the mean of those shares, the
question "was each boss taunted?". ``each`` is the taunt's measure since
issue #9: a fight with two bosses averages them, and a boss killed before
the fight ends is measured to its death. The difference is not academic:
in 95 boss fights of twelve 2026 logs, the taunt's union to the fight's
end differed from its per-boss mean in 39, reading lower by up to 83
points where a boss died early and the fight ran on against its adds.

The uptime line's six group buffs (Major Courage, Major Force, Major
Slayer, Powerful Assault, Lucent Echoes, Pearlescent Ward) and the taunt
were tracked in code until 0.8.0; they are the first seven of
DEFAULT_RULES now, so anyone can rename, edit or delete them, and the
example picker holds them for whoever wants one back. As rules they read
the same, with two differences: a group buff is measured whatever the
group size (the code needed three players), and one that never appeared
in a fight read 0% rather than being left off the line (until 0.12, when
``expected`` decided that per group size; see below). Replaying the
twelve logs (376 fights) through both: the six buffs agreed in 690 of 745
readings; in the other 55 (46 of them Major Courage, the buff refreshed
most) the rule read higher, never lower, because the code ignored an
UPDATED refresh when it had missed the GAINED before it, though the buff
was up: a 12 s fight that read 7% reads 100%. The taunt agreed in 52 of 79
boss fights and read higher in 27 (lower in one, by 5 points): the code
kept its taunt spans in the encounter, which BEGIN_COMBAT replaces, so a
taunt already on the boss at the pull was lost until the tank's next
refresh (twelve fights, a 7.7 s fight reading 0% that reads 100%), and it
measured every boss from the fight's start whether or not it had arrived,
where ``each`` measures a unit over the time it was there.

Fights without a boss: trash packs are most fights (281 of the 376, with
up to 71 mobs hit). A ``boss`` rule has nothing to measure there, so it
measures every hostile the group fought instead, and both it and an
``enemies`` rule then say how many of the pack's mobs the effect reached,
``Alkosh:45% on 7 of 12 mobs`` (the pack is the mobs the group hit, plus
any a tracked effect was applied to). In those fights Off-Balance reached up to
27 of 32 mobs with 7 at once, Major Vulnerability 7 of 18, Minor Brittle
18 of 32, the taunt 20 of 32. In a boss fight nothing changes: the boss
rule reads the boss alone (its effect was on the adds too in about half
the boss fights, almost never on the adds alone).

Dead units: the game does not always write FADED for an effect on a unit
that dies or is removed. 124 of the 376 fights ended with a span still
open on a dead or removed mob, and such a span runs into every later fight
of the zone. The engine tells the tracker when a unit dies or is removed
(forget_unit) and when the zone changes (zone_changed), which ends those
spans there.

Seen or expected (issue #13): an item is shown, as a row of the timeline
strip and in the copied text, when its effect was on a unit in scope
during the fight, or when its rule is ``expected`` in the fight's group
size: ``solo`` (one player), ``small`` (two to four) or ``large`` (five or
more), counted from the players the engine lists for the fight;
``expected`` alone, or ``all``, is every size. An expected rule whose
effect never came reads 0% on an empty row, so a missing Major Courage in
a trial stands out; a rule that is neither seen nor expected is left off.
The survey behind the defaults (2026-10-10, every tenth split log by name
within 1.5 GB: 13 logs, 196 fights of 2026): of the fourteen default
items, the number reading 0 per fight averaged 13.0 in the three solo
fights, 10.0 in the 71 four-player fights and 5.9 in the 122 trial fights.
In the trial fights the six group buffs were there most of the time
(Major Courage 96%, Lucent Echoes 86%, Pearlescent Ward 82%, Major Slayer
71%, Major Force and Powerful Assault 52%), in the four-player fights
mostly not (Pearlescent Ward 54%, Major Courage 38%, Major Force 21%, the
other three never), and the taunt in 70 of 71 four-player fights and every
trial fight. So five of the six group buffs are ``expected large``, the
taunt ``expected small large``, and the boss debuffs and Crux nothing:
they depend on who is in the group, and show when they happened.
Powerful Assault was expected too until issue #48: the set's buff is
usual in a trial group, but no role has to bring it, so a fight without
it is not a mistake worth a red 0% row, and its rule shows when the buff
was seen, like the debuffs (tracking version 4 takes the words off a
saved line again, see upgrade_rules_text). The tracker alone, without the
engine's units, knows no group size and shows every item.

Elemental Catalyst (issue #53): the set's three weaknesses (Flame 142610,
Frost 142652, Shock 142653; critical damage taken up 5% each, as pen_crit
values them) are one default rule on the boss, shown when someone applied
them and not expected. The set is an alternative to Lucent Echoes for a
group's critical damage, run where Echoes is not, so a group running it
should see it; in these logs it is rare. Every split log of 2026 (891 log
files with a fight, 607 of them veteran trials): the weaknesses appear in
4 files, two Kyne's Aegis sessions (three files are the splitter's copies
of one), both also running Lucent Echoes, which 515 of the 607 trial logs
have; no dungeon or arena log has them, and none of the 92 trial logs
without Echoes has Catalyst instead. In the two sessions the wearer was a
DPS in January (22 of 24 fights, median uptime 53%, all three weaknesses
up together 7% of a fight) and a tank in May (one fight, 78% and 51%): the
rule's uptime, any weakness up, is well above the time the full 15% is in
effect, one weakness being the usual state. A measure counting the ids up
at once, and a way to say a group needs one of Echoes and Catalyst, are
left for when the logs show the set in use.

Touch of Z'en (issue #27): the game never writes its stacks. Every
EFFECT_CHANGED line for 126597 carries a stack count of 1 (3,577 lines in
four 2026 trial logs), refreshed as a FADED and a GAINED in the same
millisecond each time the wearer applies a damage-over-time effect.
Combat Metrics derives the count instead (LibCombat's UpdateZenData):
while the player's own Z'en is on a unit, the number of that player's
effects on the unit whose ability type is damage, GAINED up and FADED
down, at most five, 0 being a reading (Z'en up, no bonus). The ``dots``
measure does the same for every wearer the log shows. The log has no
ability type, so an effect counts as damage over time when its ability id
also ticks as DOT_TICK or DOT_TICK_CRITICAL (EffectTracker.dot_tick): on
those four logs that picks out Burning, Poisoned, Hemorrhaging, Roar of
Alkosh and the class and weapon DoTs, and leaves out Off-Balance, Breach,
Brittle and the other debuffs that deal no damage. A ground area such as
Stampede ticks without an effect on the target and counts for neither.
Each wearer's Z'en is their own span (two wearers on one boss do not end
each other's), and the reading at a moment is the highest count among
them, as for ``stacks``.

A line that starts with ``$`` is a HyperTools export string, pasted as
is: HyperTools (the in-game tracker addon) serialises a tracker as nested
``$...&`` records, and its name, ability ids and target ("Yourself",
"Group", "Boss", "Current Target") become a rule here; ``stacks`` or
``on <scope>`` after the string override what it says, and ``expected
<sizes>`` after it applies to every rule it gives.

What the logs carry (nine trial and dungeon logs of 2026): the stack
count is EFFECT_CHANGED's second field and changes arrive as UPDATED
lines, so stacks are read on GAINED and UPDATED; Off-Balance on a boss
comes under several ids at once (45902 for most sources, 62988 for
Elemental Blockade, 39077, 34733, 20806, 130139), so a union is needed,
and its uptime on a trial boss was 4 to 28% per fight; Crux stacks to 3
on the Arcanist alone; a pet-applied buff (a Glyphic's heal, Major
Protection from a netch) is applied to players like any other and needs no
special case, since only the target's kind is looked at. Replaying the
bundled examples through two of those logs (Sunspire, Kyne's Aegis):
Off-Balance on the boss 12 to 28% per boss fight, to the decimal what an
independent scan of the lines gives; Crux on the logging Arcanist a mean
of 1.5 to 2.9 with a peak of 3 in every fight.

### EffectTracker

*[src/effect_rules.py:616](../src/effect_rules.py#L616)*

Open and closed spans of each rule's effect on each unit in scope,
with the stack count and the unit's kind, in raw log milliseconds;
snapshot() reads a fight's window out of them, as the timeline
recorder does.

Each id of a rule runs its own span on a unit, so overlapping ids do
not cut each other short, and the measurement merges them. A span is
closed by FADED, by a stack change (one span ends, the next begins),
by the unit's death or removal (forget_unit: the game does not always
write FADED for a corpse's effects) or by a zone change for hostiles
and pets (zone_changed: unit ids are handed out afresh). Closed spans
are pruned once the fight they belong to has been published.

### EffectTracker.snapshot

*[src/effect_rules.py:812](../src/effect_rules.py#L812)*

One entry per rule for the fight window: name, scope, kind, what
it was measured on ('units': the scope, or 'mobs' for a hostile
rule in a fight without a boss), the uptime percentage, the mean
and peak stacks while up, how many of the pack's mobs it reached
and how many there were, the text the uptime line shows, and
fight-relative intervals for a timeline.

*units* is what the engine knows of the fight's units, unit id ->
(kind, since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit ('boss' or 'enemy') with the log time each
was added and the time it died or was removed, None when not in
the fight. It says whether the fight had a boss, which mobs make
up the pack, and the window an ``each`` rule measures each unit
over. Without it (the tracker alone) the spans tell: a span on a
boss means a boss fight, and a unit is measured from the fight's
start to its death as forget_unit reported it, or the fight's end.

### CombatEncounter.fight_units

*[src/esolog_tail.py:1030](../src/esolog_tail.py#L1030)*

What effect_rules measures a fight's rules on, unit id -> (kind,
since_ms, gone_ms): the players ('self' or 'group'), and the
hostiles the group hit in this fight ('boss' or 'enemy', by the
game's flag less boss_units' exceptions) with the log time each
was added and the time it died
or was removed, None when it was there throughout. Enemies carry
over from fight to fight within a zone, so a boss that only stands
in the list, dead since the last pull, is not a boss of this fight:
it has to have been hit.

### AppConfig.reload

*[src/app_config.py:134](../src/app_config.py#L134)*

Read the file over DEFAULTS. A rules text saved before the uptime
line's group buffs and taunt became rules (tracking.version absent,
0.8.0 and earlier) kept only the user's own additions, so the line
would lose those items on upgrade: the missing ones are put in
front of it, by name, so a rule the user had already written under
the same name stays theirs. A text saved before version 3 then has
the default rules that are expected given their ``expected`` words
and Touch of Z'en's ``stacks`` turned into ``dots``, by name (upgrade_rules_text:
a renamed or already-flagged line is left alone), so a trial fight
still shows a missing group buff at 0% after the upgrade. A text
saved before version 4 has the ``expected large`` that version 3
put on its Powerful Assault line taken off again (issue #48: the
one default no longer expected). A text saved before version 5 has
the default Crux line commented out (issue #80). Nothing is written back; the
version is saved with the next Save, and every step is harmless to
repeat.

The timeline strip's old switch (experimental.buff_timeline, until
issue #25 made the strip the only view of the rules) is dropped
here, so the next Save leaves it out of the file.

## Taunts

### Taunts

*[src/esolog_tail.py:114](../src/esolog_tail.py#L114)*

The game puts one Taunt debuff on a taunted enemy whatever skill taunted, and writes a TAUNTED combat event that shares its cast tracking id with that skill's own cast and hits, which is how the skill is known: no list of taunt skills is needed, and a skill logged under another id (Destructive Clench with an ice staff is logged as Frost Clench) is matched to its bar slot by the icon the two share (mark_taunt_slots). The debuff's spans on each enemy give the uptime line's Taunt item through the default rule ``Taunt = 38254 on boss each`` (effect_rules): each boss's taunted share of its time in the fight, averaged over the bosses, the pack's mobs in a fight without a boss. Checked on 1,361 taunts in twelve logs of October 2026.

### mark_taunt_slots

*[src/esolog_tail.py:427](../src/esolog_tail.py#L427)*

Put 'taunt': True on each bar slot the player taunted with: the slot
whose ability id a taunt names, or, for a taunt logged under an id no
slot has, the slot that shares its icon (Destructive Clench taunts as
Frost Clench, a separate id with the same icon).

## What a boss is: the game's flag and its exceptions

### src/boss_units.py

*[src/boss_units.py:1](../src/boss_units.py#L1)*

What a boss is: the game's flag, and the units that carry it without being
the fight's boss (issue #67).

The encounter log flags a boss on its UNIT_ADDED line (isBoss, the sixth
field after the unit id), and the engine takes that flag as the word on
what a boss is: EnemyInfo.is_boss feeds the boss damage and boss dps time
(damage_stats), each player's boss share, the ``boss`` scope of the tracked
rules (effect_rules), the targets of the penetration figures and the
Armour row (pen_crit), and the damage window's boss-only switch. The flag
is the game's own boss health bar: it is reliable in dungeons and trials
(Z'Maja and her shade, the Lucent twins, Opulent Ordeal's three, every
dungeon boss), and the only boss definition that needs no list.

It is wrong for a few units. In Lucent Citadel the gauntlet before Xoryn
is one combat with him: the group hits five Defense Prisms (2,910,773
health, 10 to 20 s apiece) and Baron Rize (13,971,720, hit for 21 to 41 s
at about 110 s in) before Xoryn (69,858,576) is added a median 435 s into
a median 549 s fight, and all three carry the flag. Read as bosses, the
boss dps time of a Xoryn pull ran from the first hit on a Prism to the end
(a median 531 s of 561 s over 23 full pulls in 899 split logs) and divided
his damage, the Baron's and the Prisms' together; every player's boss
share counted Prism and Baron damage; a boss-scoped rule was measured on
every Prism (the taunt's ``each`` averaged over seven units); and the
penetration figures weighed the Prisms' seconds. In Kyne's Aegis the Sea
Adders of Yandir the Butcher's fight carry it too (4,657,240 health, 8%
of Yandir's, hit for about 22 s in every one of the 32 Yandir fights
logged), so the taunt was averaged over Yandir and his adders and 10% of
the "boss" damage was adder damage.

A survey over every split log on the maintainer's machine (899 logs,
9,177 fights, 2,943 that hit a flagged unit, 2026-01 to 2026-10;
scripts/survey_boss_flag.py) found no other flagged unit under a tenth of
its fight's largest flagged unit: after the Prisms (4%) and the adders
(8%) the next lowest is 20% (Baron Rize against Xoryn, and one Dreadsail
Reef pull of the Reef Guardians), then Spindleclutch's chain-pulled bosses
at 23% and Cloudrest's Shade of Z'Maja at 40%, all bosses in their own
right. The issue offered a rule instead of a list, a flagged unit under a
tenth of the largest flagged unit of its fight being an add. The survey
shows the threshold would hold, but the rule cannot be applied where the
flag is read: the largest unit, Xoryn, arrives seven minutes after the
Prisms, the tracked rules keep each span's unit kind from the moment the
effect was recorded, and the damage record keeps per-ability rows for the
bosses alone, so the fight would have to be re-kinded at its end. It would
also make the Prisms bosses on the 15 gauntlet wipes at the Baron (21% of
him) and on the wipes at the Prisms alone. A bundled list of monster ids
is read once, on the UNIT_ADDED line, so every consumer agrees.

Baron Rize is on the list, against the issue's first thought (he has a
name, a health bar and a phase of his own). The boss dps time runs from
the first hit on any boss to the last (Combat Metrics' GetBossTargetDamage,
see damage_stats), so with the Baron a boss a Xoryn pull's boss dps time
would still have been a median 446 s of 561 s, the Baron's half minute at
110 s stretching it over the gauntlet, against 129 s with him an add. The
other way out, a union of each boss's own hit window, would have changed
Nahviintaas, who lands as a new unit each time, in 27 of 136 Sunspire
fights, away from Combat Metrics' figure for a fight with one boss. A
wipe in the gauntlet before Xoryn is therefore a fight without a boss,
still named after the Baron when he took the most damage (the name follows
the most damaged hostile, flagged or not); removing his id from the list
reverses the choice.

Combat Metrics counts these units as bosses, since it reads the same boss
health bar, so its boss figures and this app's differ on Xoryn and Yandir
pulls, by design. A new trial can bring a new unit of this kind; the
survey script lists every flagged unit by zone with its health as a share
of the fight's largest, and a line here is all it takes.

## What counts as damage

### What counts as damage

*[src/esolog_tail.py:131](../src/esolog_tail.py#L131)*

A hit on an enemy is written with one of several results, and the dps figures sum the hit value of these: DAMAGE and CRITICAL_DAMAGE (direct hits), DOT_TICK and DOT_TICK_CRITICAL (each tick of a damage-over-time effect), BLOCKED_DAMAGE (what got through a blocking enemy) and DAMAGE_SHIELDED (what an enemy's damage shield absorbed). That is the set Combat Metrics (LibCombat) sums for damage done, and matches ESO Logs, which counts absorbed damage as damage done. Not counted: IMMUNE (the log writes a hit value the target never took), REFLECTED, FALL_DAMAGE, and the overflow field (overkill past the target's remaining health; Combat Metrics drops it too). Until 0.9.2 only the two direct-hit results counted: measured on 29 of Chris's split logs (990 dungeon and arena fights, 34 trial fights) the ticks were 26% of all damage dealt, and the top player's dps in a boss fight of a minute or more was understated by a median 35% in dungeons and 52% in trials, up to 79%. Shield absorbs were 2% and blocked hits 0.2%.

## Dps time and the damage window: parity with Combat Metrics

### Dps time

*[src/esolog_tail.py:154](../src/esolog_tail.py#L154)*

Every dps figure divides by the span of the hits it sums, first hit to last, floored at one second, and not by the fight time (BEGIN_COMBAT to END_COMBAT), because that is Combat Metrics' definition (LibCombat's dpstime) and the number players compare against. A player's dps is their damage over the span of their own hits, a boss figure the boss damage over the span of the hits on the bosses, the group's over the span of the group's. The fight time is still what the history line and header show; the header adds the group's dps time when it differs. The long form, with what Combat Metrics does about overkill, shields, pets and the breakdown by ability, is damage_stats' module docstring.

### src/damage_stats.py

*[src/damage_stats.py:1](../src/damage_stats.py#L1)*

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
  first hit on. The DPS graph draws both (smoothed_dps, running_dps),
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
player-fights (died, arrived late, stopped hitting). What the engine did
not count was negligible in all: hits on units the log never added 0.07% of
all damage, on non-hostile units 0.00%, in the two seconds before
BEGIN_COMBAT 0.04%, in the 1.3 s after END_COMBAT 0.02%. It was not on
single fights, though (issue #162): a group member's hit on the new fight's
enemies came in the 10 s before BEGIN_COMBAT in 43.6% of 8,765 fights. So
the group's hits from those 10 s now count, on any enemy the fight before
never hit, at their own times, and a dps time can start before the fight
does (waiting_hits). The hits after END_COMBAT still count in no fight.

### dps_time_s

*[src/damage_stats.py:99](../src/damage_stats.py#L99)*

A dps time: the span in seconds, floored at a second like LibCombat.

A span of 0 (one hit, or none) is a second, so a single hit reads as
its own damage per second rather than infinity.

### src/gui/damage_render.py

*[src/gui/damage_render.py:1](../src/gui/damage_render.py#L1)*

The damage window's HTML: one player's damage in a fight, broken down by
ability and by target the way Combat Metrics' fight report breaks it down.

The data is the fight entry's player dict, key 'damage', as
damage_stats.PlayerDamage.snapshot built it: totals, the spans the dps
figures divide by, one row per ability (and per pet ability), the same rows
for the boss units alone, and the targets hit. The figures follow
damage_stats: a row's dps is its damage over the player's dps time (over
their boss dps time in the boss view), crit % is critical hits over hits,
the average is damage over hits, and a target's dps divides by the span of
the player's hits on that target. Colors are theme-aware like the rest of
the fight pane.

### src/gui/dps_graph.py

*[src/gui/dps_graph.py:1](../src/gui/dps_graph.py#L1)*

DPS over time: a line chart of the group's and each player's dps across a
fight, drawn the way Combat Metrics' graph tab draws it (see damage_stats
for the two curves: the centred moving average over a window of seconds,
Combat Metrics' default 5 s, and the running figure, the live dps as it
stood at each second).

The data is the fight entry's group series (FightHistoryEntry.damage_series)
and each player's (the 'series' and 'boss_series' of their 'damage' dict),
damage summed per second of the fight. The tab offers the window length
(1, 5, 10 or 30 s) or the running figure, the boss units alone in a fight
with a boss, and a legend of checkboxes for the group and every player. The
first eight players (in the fight's ranking) are on to begin with and the
rest off, because eight is as many hues as can be told apart; a player past
the eighth reuses a hue with a dashed line. A player's hue is their rank in
the fight, so hiding others never repaints them.

Two panels, one scale each: the group's figure is as many times a player's
as there are players, so on one scale the players' lines lie flat along
the floor, and a second axis on the same plot is the classic way to mislead.
The group's line gets the upper panel and the players the lower, sharing
the time axis, the crosshair and the tooltip. Drawing otherwise: hairline
solid gridlines a step off the surface, 2 px lines with round joins, the
group's heavier in the pane's text colour, the categorical hues in a fixed
order (eight hues with a light and a dark step; Settings' colour-blind
option swaps in seven measured to stay apart for the dichromacies, with a
cycle of four strokes), text in the pane's own text colours and
never in a series colour, and the end value of each line labelled when a
panel shows four or fewer.

Design: The graph as a fight tab (issue #196). The graph is the main
window's DPS graph tab, beside Fight and Deaths, on the fight the list has
selected, where it was a window that kept the fight it was opened for. The
toolbar's DPS graph and the header's group dps figure open the tab. A tab
widget is as wide as its widest page: the chart's 360 px floor beside a
legend fixed at its 230 px (scaled with the text) widened the column to 729
px at 150% text and 844 px at 200%, cutting the fight list from 347 px to
231 px on every tab (probed). So the legend takes what the chart's floor
leaves, from its 230 px down to 100 px (scaled), each name elided there
and whole in its hover. The legend is named Lines drawn, and the Show
label is the mode's buddy, for a screen reader. The legend's ticks are
kept by the player's handle where there is one, a companion by its name,
which is its owner's handle and Companion (gui.fight_render), and an
anonymous player by the zone and the unit id: the game keeps a player's
unit id through an instance's pulls and gives it to another player in the
next zone, so ticks kept by the id alone went to whoever had it there, and
dropped at every pull they followed the anonymous players no further than
the fight. The mode carries across fights, and the boss switch between
boss fights; a fight without boss damage hides and clears it. The chart's
time axis takes a wider step than the timeline strip's for a long fight
when its labels would run together: the chart is narrower in the tab than
it was in the window.

The group fighting on after the fight's END_COMBAT counts in the fight
(waiting_hits, issue #162): the chart then runs to the group's last hit,
a dashed line where the fight ended, so that damage keeps its own seconds
instead of piling into the fight's last.

A moment can be marked on the chart (issue #214): an Events row asked for
with Ctrl+G is a line down both panels in the palette's highlight, with
its time and what happened at the plot's top, on the side that has room.
The chart and the Events tab count time alike, from the fight's start, so
the mark needs no conversion. It stays through the same fight drawn again
and goes with the fight. A double-click on the chart asks for the events
around the second under it (moment_requested); the keyboard's way to a
moment is the Events tab itself, whose rows the arrow keys walk. The mark
is in the chart's description for a screen reader, after its lines.

## Pets: whose damage and healing they are

### CombatEncounter.track_pet_ownership

*[src/esolog_tail.py:711](../src/esolog_tail.py#L711)*

Record *pet_unit_id* as a pet of the player who owns it, so its
damage and healing count as that player's; forget it when the owner
is nobody ("0") or not a player (a boss's summons), which also
covers a unit id handed out again.

Design: the log names the owner of every summoned unit, as
ownerUnitId in UNIT_ADDED (fields[13]) and UNIT_CHANGED (fields[8]).
A survey of nine trial and dungeon logs (October 2026) found 1,142
player-owned units, all MONSTER with reaction NPC_ALLY or FRIENDLY
(Blighted Blastbones, Skeletal Archer, Wild Guardian, Gloom Wraith,
atronachs, Clannfear, Glyphic of the Tides, companions), and 1,283
boss-owned ones; 18 unit ids were handed out again with a different
owner; and the owner field dropped to 0 on 106 pets, none of which
dealt damage afterwards (0.3 to 11 s before its UNIT_REMOVED). So
ownership follows the log exactly, and is carried into the next
fight with the players and enemies, since pets are summoned before
the pull. Pets were 0 to 8% of a group's damage per log. Earlier
code guessed pets from EFFECT_CHANGED targets and never found one.

### CombatEncounter.add_damage_to_player

*[src/esolog_tail.py:858](../src/esolog_tail.py#L858)*

Credit damage dealt by *unit_id* to the player it belongs to:
the player themself, or the owner of a pet (see
track_pet_ownership). Damage from a unit that is neither is
counted for nobody: a boss's summons, trial mechanics that hit
other enemies, and the like. *to_boss* says the target is a unit
the game flags as a boss, so the hit also counts as boss damage.
With the hit's *timestamp*, *result*, *ability_id* and *target_id*
the hit also goes into the fight's damage record (damage_stats):
the spans the dps figures divide by, and the breakdowns. With its
*damage_type*, *cast_id* and the analyzer's *cast_index* the record
also keeps the kinds of the damage (damage_kinds): the area rule
reads the cast, the session and the player-skill table, and a hit
counted single is moved to area should its cast strike a second
unit later. *area*, an (area?, rule) the cast index gave already,
stands in for the index, with no watcher, and *link*, whose the hit
is (player, companion row key or None, a pet's?) as this returned
it, for the encounter's own reading: a hit from before the fight's
line, counted at END_COMBAT (waiting_hits). Returns (the kinds'
(area?, rule), that link) as the hit was credited, None for a hit
credited to nobody.

A companion's damage is its own row's (companions.py), keyed by
the companion's row key, with its kinds like a player's; with
*accrue_companions* (the setting companions.accrue_to_owner) it is
its owner's as well.

## Split files: one per session, continued rather than copied

### LogSplitter

*[src/esolog_tail.py:5075](../src/esolog_tail.py#L5075)*

Handles automatic splitting of encounter logs into individual encounter files.

Design: one split per session, continued rather than copied (issue #85).
A session's split is named at its first BEGIN_COMBAT from the BEGIN_LOG
stamp and the zone, so a session split again meets its own file at the
rename. Until 0.18.0 the two were compared by whole-file MD5, which can
never match there (the temp file holds the lines up to that BEGIN_COMBAT,
the file on disk the whole session), so the session was written out
again under the next ``-N``: 513 of the 899 files in the maintainer's
split folder were byte-identical copies, 512 of them written by the
pre-GUI tool's ``--read-all-then-tail`` between January and April 2026,
which re-split the whole log at every start. Now the file on disk is the
same session when it begins with the temp file's bytes; the temp file is
dropped and the existing file is continued: incoming lines are counted
and skipped until the count reaches the file's size and the file's last
line has gone past, then appended, so a split cut short by a restart,
a crash or a Settings save (which rebuilds the monitor) is completed
rather than left truncated, and a split already complete gains nothing.
A file that ends mid-line (a crash) is trimmed to its last whole line
first. Only a file whose head differs is a different session of the same
second and gets the suffix. At the session's end a copy that still
matches another file of the same stamp byte for byte is removed; a
continued file never is. Two instances of the app on one split folder
(the installed app beside a launch from the source tree, which wrote
the one copy of 2026-10-25) would append to one file from two sides, so
the splitter takes a lock file in the folder, ``.esolog-tail-split.lock``
with its process id, and a second instance that finds it held by a live
process writes no splits at all and says so. Every line of the session
is written, the ones the parser rejects included (an END_CAST with a
cancel reason, an OBJECT unit), so a split is the session's bytes; the
older splits are a few hundred bytes to 57 KB short of that, which the
continuation tolerates.

### scripts/dedupe_splits.py

*[scripts/dedupe_splits.py:1](../scripts/dedupe_splits.py#L1)*

Move the byte-identical copies of split logs to the Recycle Bin (issue #85).

Until 0.18.0 a session split again was written out again under the next
``-N`` suffix: the pre-GUI tool's ``--read-all-then-tail`` did that to every
session in the log at every start, and 513 of the 899 files in the
maintainer's split folder were copies of another file, several GB in all.
The splitter no longer makes them (see LogSplitter in src/esolog_tail.py);
this script clears the ones already on disk.

A copy is a file with the same session stamp as another, the same size and
the same bytes (whole-file SHA-256, not a head hash). Of each group the file
with the lowest suffix is kept, the plain name before ``-1`` before ``-2``,
and the rest go to the Recycle Bin, never deleted outright, so a mistake can
be undone. Zipped splits and the ``keep`` folder are left alone.

```
    python scripts/dedupe_splits.py                      # list what would move
    python scripts/dedupe_splits.py --recycle            # move the copies
    python scripts/dedupe_splits.py --dir D:/esologs/splits --recycle
```

Without --dir the split folder from the app's config is used.

## A trial's result, and the fight list in blocks by instance

### src/trial_result.py

*[src/trial_result.py:1](../src/trial_result.py#L1)*

A trial's result as the game writes it: vitality left, score and time.

Design: when a trial (or an arena) is completed the log writes one line,

```
    END_TRIAL,id,durationMS,success,finalScore,finalVitalityBonus
```

e.g. ``1415661,END_TRIAL,12,1351407,T,253117,35000``: Sunspire (id 12) in
22:31, score 253,117, 35 of 36 vitality left. What the line tells, measured
on every completed run in a year of split logs (146 runs, 2026-01 to -10):

- Vitality left is finalVitalityBonus / 1000. The bonus is always a
  multiple of 1,000, at most 36,000 (a deathless Maw of Lorkhaj) and at
  least 0 (87 runs with 36 deaths or more). The 35/36 Sunspire run of
  2026-10-21 wrote 35000 with one player death in the log.
- Only veteran runs write it, trials and arenas alike: all 267 BEGIN_TRIAL
  and 245 END_TRIAL lines in the raw logs and splits (2026-11-01) are in a
  VETERAN zone, normal Blackrose Prison splits carry no TRIAL_* line, and
  UESP's Leaderboards page says scores are set in veteran mode only.
- The maximum (VITALITY_MAX) is the game's starting pool, which UESP gives
  as "typically 15, 24 or 36", and the runs fit 15 for a solo arena, 24
  for a four-player one and 36 for a trial. Measured (issue #183):
  Maelstrom Arena 15 (11 left after the 4 deaths of a solo run, which logs
  every death), Vateshran Hollows 15 (14 left, 1 death), Dragonstar Arena
  24 (a published run's banner reads 24/24; ours kept 14 with 7 of its
  deaths logged). Blackrose Prison's 24 is from a veteran banner Chris
  saw with the Unchained achievement, 24/24: every logged run used it
  all. Sanctum Ophidia's 36 is the trial rule alone, no run being logged.
  A run of an id not in the table shows the points alone.
- success is T in every END_TRIAL: a run that fails or is abandoned writes
  none, so there is never a failed result to show. An earlier veteran
  Vateshran attempt (December 2025) has BEGIN_TRIAL and no END_TRIAL.
- Vitality is the log's figure, never 36 less the deaths the engine counts.
  In 38 runs the log holds fewer player deaths than the game charged (3
  logged against 13 in an Aetherian Archive run, 8 against 23 in Hel Ra):
  the log carries the events around the player writing it, so after a wipe
  in which that player released, the others' deaths are not all there.
  Eight runs also began in an earlier split than the one with END_TRIAL.
- The name is the zone's at the time (ZONE_CHANGED), the id's from
  TRIAL_NAMES only when there is none. A split's file name can be another
  trial's: one named for Dreadsail Reef ends Kyne's Aegis (id 13).

The line comes inside the final fight in 144 of the 146 runs (33 ms after
the last hit of a Sunspire run) and so belongs to that fight. In the other
two, both Blackrose Prison, it comes about 4 seconds after END_COMBAT, and
the engine gives it to the fight it has just sent (ESOLogAnalyzer.
_handle_end_trial), which frontends then redraw. Maelstrom Arena's comes
2.9 s after END_COMBAT and takes the same path; Vateshran Hollows' and
Dragonstar Arena's come inside the final fight.

The timer is the game's, rounded to the nearest second, half up, as the
banner shows it (ZO_FormatTimeMilliseconds): 1,351,407 ms is 22:31 and
2,649,500 ms is 44:10.

### src/gui/fight_list.py

*[src/gui/fight_list.py:1](../src/gui/fight_list.py#L1)*

The fight list: the session's fights in blocks, one per instance.

Design (issue #129): the fights fought one after another in the same
instance form a block. A header row above it names the zone and its
difficulty, so the fight rows leave the zone out; when the block ended a
trial or an arena, an inert row under its last fight gives the run's
result (trial_result: vitality, score, time); and the blocks lie on
alternate backgrounds, a faint band and none, so neighbours stand apart.

A new block starts at a fight in another zone or at another difficulty
than the fight before, or at the first fight after a completed run, even
in the same zone. A wipe and a walk back in through the same door keep the
block: the zone and difficulty are the same and no run was completed. The
zone is told by its id (a solo dungeon shares its name with the group
dungeon, pen_crit.zone_kind) and by its name only when the entry has none.

Header and result rows are not enabled, so a click or a key never makes
one current: the arrow keys step from fight to fight over them, and Home,
End and the page keys go on to the nearest fight (moveCursor). Their text
takes the list's own text colour, which a disabled row would otherwise
grey out. The list therefore maps rows to fights itself (entry_at,
row_of) and offers the fight-index calls the window and tests use
(select_fight, fight_item, current_fight_index).

The band is the list's base colour moved BAND_MIX of the way towards its
text colour, so it follows the theme and keeps the text's contrast; it is
worked out again, with the header's bold font, whenever the palette or the
font changes (a theme switch, a new text size).

The (i) on a fight row (issue #147): hovering it shows who in that fight
has a possible build issue and what (fight_render.fight_issues_tooltip),
so a session's flagged fights can be read without selecting each one and
looking for the marks on the pane's rows. The row is plain text, so the
mark has no anchor of its own: viewportEvent takes the ToolTip event and
works out where the mark is drawn (issues_mark_rect), the way the style
lays the row out: the style's text rectangle, the margin every style keeps
inside it, then the width of the text before the mark. The text rectangle
matters: Windows 11's style starts it 6 px in, leaving room for its
selection bar, where Fusion and windowsvista start at the row's edge
(measured 2026-10-31 on all three and offscreen, the mark's first painted
column within a pixel of the computed one). The pointer gets MARK_SLACK
pixels either side, and the tooltip closes once it leaves that band. The
rest of a row shows no tooltip, as before. The text is built at hover
time from the hovered row's own fight, usually not the one on screen,
with the window's Hide names switch (hide_names), so it follows the switch
without a rebuild. A screen reader hears the mark as the
row's description (fight_render.issues_description), which names nobody.

Kill or wipe (issues #168 and #169, pull_outcome): a boss fight's row
carries its verdict after the boss ('Wipe 62%'), including what only the
fights after it can tell ('Cut', 'group went on'), which the engine puts
on the pull and sends the fight again for, so the row, the pane and the
copy always agree. A boss's pulls in a row get an inert run row under the
last of them ('Lord Falgravn: 13 pulls, best 48%, 9 wipes at 80 to
90%'), above the run's result row when it ended a trial; hovering it
adds the first death of each pull, the killers and the players longest
dead, names through the Hide names switch. Each new or updated fight
redoes its block's run rows (_refresh_runs) from the block's own rows,
so a run row moves down as the run grows and a refresh never walks the
whole list.

The instance (issue #196): a click on a header, run or result row opens
the window's Instance tab on that row's block (instance_requested,
instance_of), a run row's at that boss. The rows stay inert, so the
current row is always a fight and every caller of current_entry() still
gets one. Qt 6.12 sends itemClicked for an inert row, but does not
promise to, so the list tells the click itself: the row the left button
went down on, and its release on that same row (mouseReleaseEvent); a
drag to another row, or another button, opens nothing, nor does the
double-click a click on an inert row begins: Qt makes it a second press,
which opened the instance again, or, the first click having selected a
fight and scrolled the list, selected whatever fight came under the
pointer. The rows show they can be clicked with the pointing hand, set
again as rows move under a pointer that does not (a scroll, a fight
coming in), once the rows have moved, and
the hover line INSTANCE_CUE, which a run row's hover text ends with; a
screen reader hears INSTANCE_DESCRIPTION as their description, after a
run row's own.

## Kill or wipe, time dead, and a boss's pulls in a row

### src/pull_outcome.py

*[src/pull_outcome.py:1](../src/pull_outcome.py#L1)*

Pull outcome: whether a boss fight was a kill or a wipe, the boss's health
when it ended, each player's time dead, and a boss's pulls in a row
(issues #168 and #169; engine side and plain text, no Qt).

Design: the log writes no verdict, so a fight's ending is read from what
the log shows of the boss and the group. The log shows what happened
around the player writing it, and an ending that player did not see must
never be called a wipe: ESO Logs sometimes calls a kill a wipe (the
maintainer's warning, 2026-11-01), and so did the first versions of these
rules. Each rule below was checked against what the group did next, the
same boss again or the next boss, on the split logs of January to October
2026 (378 sessions once byte-identical copies are dropped). Replayed
through the engine they hold 2,362 fights with a pull: 1,548 kills, 708
wipes, 40 lost sight and 66 left. Of the non-kills, 736 were followed by
another pull of the same boss; 18 were never pulled again while another
boss came after, and none of those reads as a missed kill: Infinite
Archive runs that ended, a Turlassil wipe with all twelve dead, Cloudrest's
shades, and a few seconds-long scripted starts.

- **The boss** is the named unit the game flags as a boss (less the units
  boss_units demotes) that took the most of the players' damage. Unnamed
  boss-flagged units, a mechanic's helpers, took more in 143 fights and
  never decide. The pull's bosses are that unit and every other named
  boss unit with BOSS_SHARE or more of the boss damage, so encounters whose
  top unit alternates from pull to pull (Lylanar and Turlassil, Positrox
  and Negatrix, Reactor and Reducer) stay one encounter: grouped by the
  top unit alone, 50 wipes looked like a group moving on to another boss,
  grouped by shared bosses 25, every one of them a real wipe (arena and
  Infinite Archive runs that ended, gauntlet resets, nights that gave up).
- **Kill**: the boss's death line (DIED, or DIED_XP, which in 13 fights
  carried the only 0 health a health-only rule would have missed), a line
  showing it at 0 health, the run's END_TRIAL inside the fight, or its
  health under LOW_HEALTH_KILL_PCT at its last line with fewer than half
  the group dead when the fight ended. That last test caught 5 fights
  whose death line never reached the log (Tremorscale at 0.2%, Eliam
  Merick at 0.1%): none was pulled again, and 4 were followed by the next
  boss. A kill with half the group dead is still a kill: 174 fights. A boss
  left under NEAR_ZERO_KILL_PCT with one of the group standing died: once
  the deaths the log writes no line for counted (issue #221), Sanity's
  Edge's Archwizard Twelvane, who leaves his phase at 7 of 124 million
  health and writes no death line, read as a wipe with exactly half the
  group dead, the Chimera kill beginning 0.6 s later. Over the 391 split
  logs no other pull ends that close to 0 without a kill. With every
  player dead it stays a wipe, however close.
- **Wipe**: not a kill, and at least half the fight's players were dead
  when it ended, not revived before END_COMBAT. "Half the group died at
  some point" is the wrong test: in a long fight with resurrections every
  player can die once while the group goes on to kill the boss.
- **Lost sight** (UNSEEN): neither, and the logging player was dead when
  the fight ended. BEGIN_COMBAT and END_COMBAT follow that player's own
  combat state, so their death ends the log's fight (a median 9 s later)
  whatever the group does next. "group went on" is added when a later
  pull in the instance is of another boss and this one never returns,
  which is the log's only trace of a kill it did not see. It is said of
  Lost sight only: a wipe or a reset followed by the next boss is a group
  that gave up on that boss, not one that killed it out of sight.
- **Left**: none of these; the group reset or walked away.
- **A late verdict**: a death logged just after END_COMBAT
  (LATE_DEATH_GRACE_MS) and an END_TRIAL logged after the fight was sent
  (an arena's, about 4 s later) change the sent pull, and the engine sends
  the fight again.

A first version also called a pull a wipe when another boss unit with 10%
of the damage was left standing with half the group dead (twin bosses):
of the 20 fights that turned into wipes, 15 were never pulled again and
the group went on to the next boss (the unit left was a helper or
Archwizard Twelvane at 0%), so the rule was dropped; 3 real twin wipes now
read as kills, and the next pull of the pair shows the group still at it.

Time dead: a player's DIED, KILLING_BLOW or KILLED_BY_SUBZONE (a fall,
issue #184) opens a span, and so does a death the log wrote no such line
for: the player's state reading health 0 for ZERO_HEALTH_HOLD_MS with no
death line (issue #221, see death_recap), the span from the first 0. The
next combat line that carries their state with health above 0 closes it,
at least REVIVE_MIN_MS after the death, since the lines of the killing blow
carry the corpse's 0. A corpse's own states close none: its healing ticks
write health with magicka and stamina at 0, and its regeneration tick
writes health equal to its own regeneration, which later lines repeat for
seconds (#221, esolog_tail's _note_zero_state). END_COMBAT closes any span still open, and those still
open are the players dead when the fight ended. A fight the game cut in
two (COMBAT_RESUME_MS), or carried on while the group fought on
(waiting_hits), reopens them, but for a player up again between the
lines, dead until then; a death between the lines is the fight's too
should it carry on. A span starts at the fight's start
at the earliest: a player who fell before the pull is dead from it, not
from the fall. Deaths the log never saw (the others' after the logging
player released) are missing from the counts, so time dead, read from
each player's own states, is the fairer measure of who spent the fight
on the floor.

A pull the log cut in two: when the logging player dies the fight ends
for the log, and when they are revived a new one begins on a boss still
part way down. A fight that begins within CONTINUE_GAP_S of the last
pull's end, on a boss that pull shared, with that boss's health under
CONTINUE_MAX_PCT and within CONTINUE_DRIFT_PCT of where the last pull left
it, ``continues`` that pull: the fights stay two entries with their own
figures (the dps stays Combat Metrics' per fight), and the pull count
takes them as one. The earlier fight reads "Cut". The players still dead
when the earlier fight ended stay dead into the later one until a line
shows them up (TimeDead.carried), so a wipe that spans the cut is still
a wipe; a fight that does not continue the last pull ignores them, since
after a wipe the dead release and run back unseen.

Pulls in a row: the pulls of one block (gui.fight_list: one instance)
that share a boss, with fights without a boss between them, form a run
until a kill. A run of two or more pulls gets a summary row: the pulls,
the kill or the best pull, the wipes that keep ending in one band of
WALL_BAND_PCT (WALL_MIN_WIPES or more, half of them in the band), and the
median time between pulls; its hover adds the first death of each pull,
the killers over the run and the players who spent longest dead.

## The session recap: the fight list as text for Discord

### src/session_recap.py

*[src/session_recap.py:1](../src/session_recap.py#L1)*

The session recap (issue #171): the fight list as plain text for Discord,
for the raid lead who posts the night, not one fight.

Design: the recap is the list's own two groupings written out. Each
instance block (fight_blocks) gets a heading with its zone, the time it
spans and the group's size; under it, one line per boss's pulls in a row
(pull_outcome.runs), in the order they were fought; then the trash, as a
count and a time; then how many players had a possible build issue; then
the run's result when the block completed a trial. A boss killed on the
first pull is one line with the kill's time and boss dps. Two pulls or
more are the run row's summary, the kill's time and dps after it, then
its hover's lines (first deaths, killers, longest dead) indented under
it: what ended the pulls is the part of a progression night nobody wants
to retype.

The copy is plain lines: Discord keeps the breaks and wraps them on a
phone, where a code block would run off the side. A message is 2,000
characters at most; a long night is pasted in parts, and the status bar
says how long the copy is. Every player name goes through the Hide names
mask, the only names being the run's longest dead; build issues are a
count, never names, since a recap posted to a channel is the wrong place
to call players out.

The sums in the data the lines come from (2026-11-01, 378 split
sessions): a median session had 18 fights, 4 boss fights over 3 bosses
and 15 minutes in combat (p90 44 fights), so a typical recap is under 15
lines.

### src/fight_blocks.py

*[src/fight_blocks.py:1](../src/fight_blocks.py#L1)*

The fights of one instance, as the fight list groups them (issue #129),
in one place with no Qt: gui.fight_list draws them as blocks, the engine
reads the newest one for the pulls' 'Cut' and 'group went on'
(pull_outcome.mark_context), and the session recap writes one per block
(session_recap). gui.fight_list's docstring has the design.

A new block starts at a fight in another zone or at another difficulty
than the fight before, or at the first fight after a completed run, even
in the same zone. The zone is told by its id (a solo dungeon shares its
name with the group dungeon) and by its name only when the entry has none.

## Fight history across sessions: the index of boss fights

### src/fight_index.py

*[src/fight_index.py:1](../src/fight_index.py#L1)*

Fight history across sessions (issue #170, no Qt): every boss fight's
figures in a JSON Lines file beside the config, read back so a pull is set
against the group's own earlier kills of the boss, and a player against
their own.

Design: the fight history (fight_history.FightHistory) lives for a
session, and the split logs the app writes are never read again, so a kill
had nothing to be read against. The index keeps one line per boss fight
(a fight with a pull, pull_outcome), kill or not, written by the GUI when
the engine sends the fight and again when it sends it updated. Nothing is
parsed for it: the line is the entry's own figures. Builds are not kept.

- **Where**: ``fights.jsonl`` beside the config (the AppConfig folder,
  ``%LOCALAPPDATA%\esolog-tail`` on Windows, ``~/.config/esolog-tail`` on
  Linux), never in the split folder, so split retention never deletes it.
  Plain JSON Lines, one object per line, handles in clear as in the logs.
- **Key**: the fight's start in Unix seconds (pull['start_s'], the
  session's BEGIN_LOG time plus the fight's own offset), so the live
  fight, its replay at the next start and a backfill of its split file all
  write the same key. A line is only appended when it differs from the one
  already held under its key, and readers take the last line per key: an
  update appends, a restart's replay of the session appends nothing.
- **A bad line**: a line that does not parse (a crash halfway through a
  write, a hand edit) is skipped and counted; the rest of the file reads.
  A file another program holds open (a sync client) keeps its lines
  queued and retries at the next write, never raising.
- **Backfill**: the split folder's logs (and the logs in its zips), newest
  first, through the engine itself (review_load.replay_log), on the
  review thread with its cancel and progress, so every figure is the
  app's own. Byte-identical copies, zipped or not, are skipped by a hash
  of their first 256 KB and their size. A session's re-splits that the
  old splitter cut short (issue #85) are read too, shortest first, so
  where two hold one fight the longest log's line is the one kept: in the
  maintainer's folder 20 such logs in 10 sessions. The live log's newest
  session is left out: the splitter may still be writing its split (the
  temp name lasts only until the zone is known), and the window indexes
  that session itself as it replays and follows it. Each log done is
  noted in ``fights-backfill.json`` beside the index, by its own name
  (which a zip of it keeps) and with its copy mark, once its lines are
  written, so a cancelled backfill carries on where it stopped. A first
  build of the maintainer's split folder (398 logs, 36.8 GB) took 44
  minutes on one thread, 13.8 MB/s, and wrote 2,414 lines, 3.0 MB.

Comparisons (the issue's measurements: 179 bosses killed, 23 in 10 or
more sessions; Lord Falgravn's kills 265k to 953k; a standing Sunspire
group shares 10 handles between sessions while Kyne's Aegis and Lucent
Citadel pugs share one, and 8 or more named players in three fights in
four):

- **The pull** in the fight pane: the group's boss dps (all damage in a
  fight with no boss figure) against the earlier kills of the same boss
  at the same difficulty in the same zone, always, and against a narrower
  set when one holds enough: kills with ROSTER_MIN or more of tonight's
  named players on the same game version when SET_MIN or more remain, else
  those kills on any version when SET_MIN or more remain. The line names
  the set it used. Only kills before this fight count, so a fight read
  later is set against its own past.
- **A player** in their name's hover: their boss dps in their last
  PLAYER_LAST kills of the boss in the index, with you (the logging
  player) or as you.
- **A boss's pulls in a row** (gui.fight_list's run row): the best earlier
  kill of the boss with ROSTER_MIN or more of the run's named players.

Anonymous players (no handle in the log) are kept without one and never
matched. The game version is the session's own (BEGIN_LOG), so a patch
narrows the set by itself.

## Death recaps

### src/death_recap.py

*[src/death_recap.py:1](../src/death_recap.py#L1)*

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
- Some player deaths have no death line at all (issue #221): 1,366 of the
  17,976 deaths in fights in the maintainer's 391 split logs (7.6%), from
  7.1% in dungeons to 8.0% in arenas. The player's state reads health 0,
  they stay down, and they come back by a resurrection or a release. The
  engine counts such a death when the player's state, on any line that
  carries it, reads 0 for pull_outcome.ZERO_HEALTH_HOLD_MS and no death
  line names the player meanwhile (esolog_tail's _note_zero_state); one up
  again sooner was no death. It is timed at the first 0. Its killer and
  ability are the hit that left the player at 0: the line that first
  showed the 0, or one logged up to KILLING_BLOW_GRACE_MS after it
  (blow_fields), else the last hit on the player at or before it,
  KILLER_WINDOW_MS back at most (last_hit_fields; often a hit of 0 with
  the overkill in the overflow), else NO_HIT_DEATH. The recap carries
  cause HEALTH_CAUSE so a frontend can say the death was read from health.
  A death line up to pull_outcome.ZERO_LINE_SAME_MS after it, the player
  not seen up between, is the same death written late, and keeps that
  recap. Each player's history is kept that hold longer than the window,
  so the corpse's hits and heals in the hold cut neither the recap's
  window nor the killer's.
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

The window is a setting (issue #95): 1 to 10 seconds, read from the config
when the engine is built (app_startup), so a Settings save, which rebuilds
the engine and replays the session, rebuilds the fights already listed with
the new window. Each recap records the window it was built with
('window_ms'), so a frontend names the right number of seconds for a fight
recorded under another setting, and a recap from before the key existed
reads as the old fixed five (LEGACY_WINDOW_MS).

The default is 3 (issue #133, 5 before). Replaying 24 split logs of
October 2026 (1,550 player deaths, mostly veteran trials) with a 10 second
window and measuring each narrower one against it: the drop from half
health to the death fits in 3 seconds for 71% of deaths (77% at 5, 41% at
1), in a table of 5 rows at the median (7 at 5). What 3 gives up is the
biggest hit of the last 10 seconds in 9% of deaths (6% at 5) and the last
heal in 13% (9% at 5). 1 second is a "what killed me" view: three rows at
the median, and in 28% of deaths nothing the Killed by line does not
already say. No window came out empty, since the killing blow is logged up
to KILLING_BLOW_GRACE_MS after the death. Only new installs get 3: the
main window saves the whole merged config on close, so everyone on 0.20.0
or later has a stored 5 that cannot be told from a chosen one, and it is
kept.

A recap also carries the dying player's own casts in its window ('casts',
issue #214), which the recap's table shows among the hits and heals, so a
reader sees what the player was pressing as the damage came in. They come
from the engine's cast recorder (casts.CastRecorder) when the death is
counted, by its rules: one cast per castTrackId, begun in the window up
to the death, a proc the game writes as a cast over and over left out
unless it is of a skill on the player's bars. They are kept apart from
'events', so the window's sums by kind never count them.

## Kinds of damage: direct or over time, area or single target, Martial or Magical

### src/damage_kinds.py

*[src/damage_kinds.py:1](../src/damage_kinds.py#L1)*

The kinds of damage: direct or over time, area or single target, Martial or
Magical, and what shields, blocks, heals and overheal did (issue #73).
Engine side, no Qt. The death recap and the build window draw the same
summary from the same rules, so a reader learns one vocabulary.

Design. The Warfare champion point stars act on four splits of a hit, and
the encounter log carries three of them on every COMBAT_EVENT line:

- **Direct or over time** is the result: DAMAGE, CRITICAL_DAMAGE and
  BLOCKED_DAMAGE are direct, DOT_TICK and DOT_TICK_CRITICAL are over time
  (Master-at-Arms and Thaumaturge for damage dealt, Ironclad and Enduring
  Resolve for damage taken). FALL_DAMAGE is neither and is named "fall".
- **Martial or Magical** is the damage type: PHYSICAL, BLEED, POISON and
  DISEASE are Martial (Mighty, Hardy), MAGIC, FIRE, COLD and SHOCK are
  Magical (War Mage, Elemental Aegis). OBLIVION belongs to neither and no
  star reduces it; DROWN, GENERIC, NONE, EARTH and any type a later patch
  adds are "untyped" and shown under the log's own word, never refused.
  Over 87 of Chris's split logs (11.6 million combat lines, 6,831 player
  deaths; 2026-10-27) the damage that reached players' health was 885M
  Magical, 411M Martial, 44M Oblivion and 20M fall, drowning or untyped,
  89% of it direct and 11% ticks; the death lines by type were MAGIC 1,434,
  PHYSICAL 1,391, SHOCK 1,257, FIRE 1,053, OBLIVION 770, COLD 587, POISON
  243, GENERIC 59, BLEED 17, DISEASE 17, DROWN 3. EARTH appeared on five
  hits, NONE on REFLECTED lines and on the zero-value DAMAGE line the game
  writes beside a DAMAGE_SHIELDED line when a shield took the whole hit.
- **Blocked, absorbed, avoided.** A BLOCKED_DAMAGE hit value is what got
  through the block and counts as direct damage; how much the block
  prevented is not in the log, so it is never stated. A DAMAGE_SHIELDED
  line is what a shield absorbed and is never added to the damage that
  reached health (shields absorbed 726M on players in the survey, more than
  any one damage type reached health). DODGED and MISS are counted, not
  summed. IMMUNE and REFLECTED are not counted.
- **Healing.** HEAL and CRITICAL_HEAL are direct heals, HOT_TICK and
  HOT_TICK_CRITICAL heals over time (Focused Mending, Swift Renewal); the hit
  value is healing received and the overflow is overheal (1.17B received against 12.4B
  overheal in the survey; 3.1M of 3.6M heal lines were pure overheal).
  HEAL_ABSORBED is healing a healing-absorb effect ate. The killing blow's
  overflow is overkill (written on 6,039 of 6,398 killing blows; a blow
  written as BLOCKED_DAMAGE or FALL_DAMAGE carries none).

**Area or single target is not in the log** (Biting Aura and Deadly Aim,
Unassailable and Duelist's Rebuff), and is read from the cast id. Every
hostile hit on a player in the survey carried a non-zero castTrackId, and
grouping hits by (source unit, cast id) separates the mechanics that kill
groups from the attacks that pick one player: Maelstrom's 147 casts struck
up to 12 players each, Grievous Pulse's 38 casts struck more than one player
every time, Oppressive Bolts' 266 casts 98% of the time; Piercing Hailstone,
Venom Injection, Temporal Splinters, Swipe, Claw and Clash struck one unit
per cast, always. So a hit is area when its cast struck two or more distinct
units in the fight, counting hits before and after it; a hit of a cast that
struck one unit is area when a cast of the same ability struck two or more
earlier in the zone session (a repeat pull of the same boss); for a player's
or pet's own ability with no such evidence the bundled table of player
skills' target kinds decides (data/skills/ability_targets.json, Area, Cone
and Ground against Enemy, from UESP's skill table); otherwise single target.
Monster abilities never consult the table: UESP's target field calls
Oppressive Bolts and other group-wide mechanics "Enemy", and knew only 74%
of the hostile damage in the survey, so for monsters the log is the better
judge. The rule that classed a hit is kept beside it, so a reader can be
told "this cast hit 8 players" or "no cast of this ability struck two
players this session". Melee against ranged is not attempted: the log has no
range, its unit positions are normalised map coordinates whose scale differs
by map, and no Warfare star reads it.

A session's cast index and a fight's damage-taken tallies cost a few
dictionaries: the (source, cast) map is cleared at each fight's end, the
per-ability memory with the zone session (unit ids start over), and a cast's
pending amounts are dropped the moment it hits a second target.

## The damage taken window: by source and by healer, over the whole fight

### src/gui/taken_render.py

*[src/gui/taken_render.py:1](../src/gui/taken_render.py#L1)*

Damage taken window: one player's damage taken and healing received over a
whole fight, by kind, by the unit that did it and by the unit that healed
(issue #98). The death recap keeps the last seconds before each death and
is only there for a player who died; this window has no event table, only
the fight's totals, so it opens for any player.

Design. What a tank wants to know after a pull is what hit them, who hit
them and whether the healing kept up, none of which the fight pane or the
build window says. The data is the player dict's 'taken' key, as
damage_kinds.TakenTally.snapshot writes it for every player in every fight.
The shape follows a survey of three veteran trial logs (Dreadsail Reef,
Sunspire, Halls of Fabrication; 48 boss fights of a minute or more, 561
player-fights with damage taken; 2026-10-27):

- Every ability is listed, no cap. A tank took damage from a median 11
  distinct abilities (at most 26) and 8 units (at most 29), a DPS from 7
  and 5 or 6; the ten largest abilities carried everything in the median
  fight, so the table is short enough to read whole.
- Damage is grouped by the unit that did it, bosses first. The largest
  source carried about half the damage and the second a fifth, so "the
  boss against the adds" is the first question; units of one name are one
  row with their count, since adds come in packs (four Alkosh's Will on
  Nahviintaas). Bosses carried a median 44% of the damage taken in every
  role. The unit the log leaves unnamed (id 0: the environment, fall
  damage, some set procs) is its own row.
- The per-second figure divides by the fight time, pull to end, not the
  span of hits as the dps figures do: it is for comparing pulls, a quiet
  stretch is part of the answer, and the hits spanned only 64-80% of the
  fight (tanks most). Tanks took a median 1,016 a second, DPS 545, healers
  512.
- Healing is grouped by healer, with the healer's abilities under them.
  Six to eight units healed each player in the median fight (every group
  HoT counts) with 15-19 abilities between them; the largest healer gave
  51-65%, a tank's own heals 23% of what they received, a healer's own
  61%. A pet's heals (a Twilight Matriarch's) are a row of their own named
  after the owner, since the log names no pet.
- Overheal is a share per row, never an amount: 91-96% of all healing on a
  player overflowed, so the amounts would be ten to twenty times the received
  figures and bury them. Healing received is the headline; the share tells a
  healer which HoTs were wasted on this player.
- Shields absorbed 54-67% as much again as the damage that reached health
  (tanks most), so the header gives the absorbed amount with that ratio,
  and the blocked hits as a count of the direct hits that reached health
  (tanks blocked 1,818 of 5,729 in the survey). What a block, armour or
  resistances prevented is not in the log and is never stated.

The kinds bars are the death recap's block (death_render.kinds_block_html)
so the two windows read alike; the player names go through the Hide names
mask (gui.name_mask), the sources and healers included.

## The player window: one window, a tab for each link

### src/gui/player_window.py

*[src/gui/player_window.py:1](../src/gui/player_window.py#L1)*

The player window (issue #196): one player's fight on seven tabs, in place
of the build, damage, damage taken and death recap windows.

Design: One window for a player. Each player link on the fight pane opens
this one window at the tab for that link: the name and the lone mastery's
'?' at Build, the dps figure at Damage done, the 'p:... cd:...' token at
Pen and crit, the shield at Damage taken, the skull and the Also died chip
at Deaths. Four windows to place became one, and the build page, which no
window fitted (2,352 px at the median), became pages that mostly do.

```
    Build · Damage done · Pen and crit · Resources · Damage taken ·
    Healing received · Deaths
```

Each tab is a FightView drawing one part of the four pages (build_render,
damage_render, taken_render and death_render, each with header=False), under
two header rows the window draws itself: the previous player button, the
player picker, the next player button and Boss targets only (shown on Damage
done); then the fight line and Show in list. The order is the build window's
(#143: gear, then what the player did with it, the cap sections and
Resources), then the damage taken side. The kinds of damage dealt moved from
the build page to Damage done, beside the damage they sort, and the death
recap's closing block of the whole fight's damage taken became a link to
the Damage taken tab, which has all of it (decision 4, reversing that part
of #95). The damage taken page is two tabs, its healing received line a link
to the second (decision 1).

The window keeps the fight it was opened for, as the four windows did
(#143): a pane link binds the pane's fight and the player and names the tab,
and the tabs, the picker and the links in the pages work on that pair,
never on the list. The fight changing in place (entry_updated) redraws the
page on screen, each other page when it is next shown, each keeping its
scroll; a burst of updates (mark_context and the mastery backfill send one
per earlier fight) draws once, on the event loop's next turn. A Settings
replay builds new entries: MainWindow puts the window on the replayed copy
of its fight, found by its key and checked by the player's handle, and
leaves it on the old one, saying so, when there is none.

Tabs that do not apply stay enabled and say so in a line (Qt moves off a
disabled current tab). The Alt letters are the tab labels' mnemonics and
never shortcuts too: a key bound twice in one window works every other
press (probed on PySide6 6.12.0). Ctrl+PgDn and Ctrl+PgUp change the tab
from anywhere in the window, Ctrl+Down and Ctrl+Up the player, keeping the
tab. Opening puts the focus in the page; an Alt letter or Ctrl+PgDn from the
header rows moves it into the new page, since Qt leaves it in the picker,
where PgDn changes the player. A link reached with Tab has Tab's focus
again when its tab is shown again, as it kept it between the four windows:
Qt drops it as the tab widget hides the page (FightView.give_link_back).
The window has no Close or default button, so Enter never closes it; Esc
and the title bar's x hide it.

It holds no reference to MainWindow: it asks for its fight to be shown in
the list by a signal, and its pages' links are its own tab switches, but
for a death's Positions and Events links and the This player's actions
button beside Show in list (issue #214), the ways out of it, which it hands
on by signals too, with its fight: the positions window and the Events tab
are the main window's. The button is on for a player row whose casts the
fight kept while the fight is in the list. It stores no lambda on a child.

## The fight's tabs: Fight, Deaths and Instance

### src/gui/fight_tabs.py

*[src/gui/fight_tabs.py:1](../src/gui/fight_tabs.py#L1)*

The fight's tabs (issue #196): the main window's right column, under the
review banner, as tabs on the fight selected in the list, with the search
in the tab bar's corner.

Design: The fight tabs. The list's fight is shown on tabs: Fight, the buff
timeline strip and the fight pane as they were; Deaths, every death of the
fight on one page (fight_deaths_render); Events, the fight's notable
events as a table (events_tab, issue #214); the DPS graph (dps_graph); and
Instance, the instance the fight belongs to, its block of the list
(instance_render). The tabs show the fight the list has selected, so this
level cannot go stale, where the player window keeps the fight it was
opened for. The tab chosen stays when the fight
changes, new live fights included, and is not kept from one run of the app
to the next. The Alt letters are the labels' mnemonics; Ctrl+PgDn and
Ctrl+PgUp change the tab from anywhere in the window, the list included.

The search sits in the tab bar's corner, so the Fight page keeps its
height: a row of its own cost the pane 30 px. It searches the page on
screen, and its count follows that page. The count is drawn inside the
field, at its right end, before the clear button: beside the field, as it
was, it clipped the tab labels at 190-200% text (probed with the window's
own text). The field takes the width the bar leaves, at most about forty
characters (260 px at 100% in Segoe UI). When the bar leaves less than the
widest count ('999+ matches') and about six characters, at a large text
size in a narrow column or in a wide font (at 200% in Segoe UI the five
tabs' labels need 517 px of the 705 a 1080 px window gives the column,
leaving 188 where the field needs 267), the corner holds a Find button
instead (issue #214; the maintainer's decision: "the search field shrinks to a
button at large text, so no page loses 48 px"). The button, or Ctrl+F, shows the
field on a row of its own above the tabs while the search is in use; Esc
on the empty field, or leaving it empty, hides the row and gives the
button back, with the focus after Esc. A search with text keeps its row,
and its count, until it is cleared. When the field took that row whenever
the corner was short, every page lost the row's height for as long as the
window was narrow. The field is placed again as the column's width, the
text size or the tabs change, so the bar is never narrower than its labels
and the button together, and none hides behind Qt's scroll arrows; a
search in use, or the field with the focus, goes on on its row as the
corner shrinks.

With no fight to show (the page before the first fight, a Settings
replay), the Fight tab is on screen and the bar and the field (or the
button) are hidden together: hiding the bar alone left the field a control 0 px tall that took
the focus, and Ctrl+PgDn still switched the pages (probed on PySide6
6.12.0). The window's Ctrl+F, Ctrl+PgDn and Ctrl+PgUp do nothing then, and
the hidden bar's Alt letters do not fire, until a fight brings back the tab
chosen.

### MainWindow._show_fight

*[src/gui/main_window.py:1671](../src/gui/main_window.py#L1671)*

The current fight on the fight's tabs (the list's
currentRowChanged passes the row, which a header row never is).
*search_from*, for the page redrawn in place, is where the reader
had the text cursor among the search's matches on the tab on screen
(_search_place): the search goes on from there (_apply_search).
*others* False leaves the other tabs' pages as they are, for a
change to the Fight page alone (Detail view).

The Fight page, the strip and the pane, is always drawn, as the
issue's design has it: one path for the pane, which the list's
selection, Hide names, the theme, the text size, Detail view and
the pen/crit settings all draw through, and a fight changes in place
only a few times (a late death, its banner, a mastery found later).
Then the tab on screen, if it is another, in place when it shows
this fight already (the Instance page: this fight's instance, the
search going on from its place; the Events page: its row selected
and its scroll kept, gui.events_tab); the other tabs are marked, and
drawn when they are next shown, the search going on where it was on
a page drawn while hidden (_on_fight_tab_changed, gui.fight_tabs,
issue #196).

### src/gui/fight_deaths_render.py

*[src/gui/fight_deaths_render.py:1](../src/gui/fight_deaths_render.py#L1)*

The fight's Deaths tab (issue #196): every death of a fight on one page,
where the fight pane has a chip on each player who died and a line on the
first death.

Design: The deaths of a fight, together. The page opens with a summary line
('12 deaths of 12 players · first at 1:03 · the pull ended 27s after it ·
12 dead at the end'), then one table of the deaths in time order: when, the
player's role, the player, what killed them with its icon, from whom, and
how long they stayed dead. Under it: what killed the group, each ability
with its source and counted, a fall or lava among them (#184), and the
share the pull's bosses dealt; each player's time dead in all, longest
first, with its share of the fight; and last the companions' deaths, as a
count, since the log keeps no recap of them. Each name links to that death
on the player window's Deaths tab (death_render.recap_href), with a hover
that says when and to what. A player the fight's table does not list (the
pane's Also died) is listed like any other, with no role. A player the log
gives no name, 'anon', has its row's class beside it, and in the time dead
line its role too, as the opener's line has (fight_render): several anons
would read as one.

How long one death kept the player down is known in two cases, and given
only in those. A player's only death in the fight lasted their time dead
(pull_outcome.TimeDead), unless the fight carries on the last pull, when
that time can hold a span carried from the fight before. A player's last
death, when they were dead at the end, lasted to the fight's end. The
engine keeps time dead by player, not by death (no revive is kept), so a
player's other deaths show a dash, which a note under the table explains,
and their total is in the time dead line. Who was dead at the end is kept
only with a pull (a fight with a named boss the players damaged): the page
of a fight without one says nothing of the end.

Where everyone stood (issue #214). In a fight whose lines the app can read
again (death_render.positions_known: the engine gave it a locator, with
its session known) each row's time is a link to the positions window at
that death's moment, the player who died selected; its hover says
'Positions at 0:54'. The link carries the moment, never the death's
number, which a death the game writes late shifts. It is in the link
colour, as a time gives no other sign of being a link. It takes no room of
its own: a column of its own, after Dead for, took the room the 22% shares
of Player and From are laid out in, so at 150% and 200% text the killer's
name broke, at 200% in a 1600x900 window a letter a line ('Lieutenant
Njordal' in 13 lines, the page 415 px high going to 703), and Killed by
broke too; the table's least width, which the first test measured, never
showed it, text being free to break anywhere. With the time as the link,
From, Killed by and the page's height are as they are without it, at 150%
and 200% in a 1366x768 window (test_positions_wiring_gui). A fight without
a locator draws the time as plain muted text.

Nothing here changes the entry: the engine's thread updates an entry in
place while a page is drawn, so its lists are read with sorted() and
copies, never sorted in place.

### src/gui/instance_render.py

*[src/gui/instance_render.py:1](../src/gui/instance_render.py#L1)*

The Instance tab (issue #196): the trial, arena or dungeon run the fight
on screen belongs to, on one page, where the fight list spreads it over a
header row, run rows and their hover, a result row and Copy session.

Design: The instance page. An instance is a block of the fight list
(fight_blocks.blocks: the fights fought one after another in one zone at
one difficulty, closed by a completed run, #129), taken anew at each
drawing. The page reads, from the top:

- **Heading**: the zone and difficulty, the time from the first fight's
  start to the last one's end, the fights, the group's size and the game
  version, the span and the size as the session recap writes them
  (session_recap.span and players), then Copy this instance, which copies
  the block as Copy session writes each instance (session_recap.recap_text,
  #171). The live list's first instance can have begun before the logging
  session the app read at its start, since a start reads the log's latest
  session only (LogFileMonitor._load_latest_session), so that page says
  it is listed from its first fight and that any earlier fights are in
  the previous session's log: "any", since mostly there are none.
- **Result**: a completed veteran trial's or arena's result, as the result
  row writes it (trial_result), with the fight pane's Score banner links,
  which act on the fight with the result whichever fight is on screen;
  under it the split logs of the instance's sessions, as the result strip
  lists them (gui.fight_render.split_lines_html, #194). A dungeon or a
  failed run has no result, only a veteran run that succeeds writes
  END_TRIAL, and its strip holds the split logs alone.
- **Bosses**: a row for each boss's pulls in a row (pull_outcome.runs),
  one pull included: the pulls, the result, the kill's time and boss dps,
  and the deaths over all its pulls. The result is the run row's words
  after its count ("killed on pull 3, 41s between pulls"), or one pull's
  verdict ("kill", "wipe 62%"), then the best earlier kill with this
  roster from the fight history (fight_index.run_best_kill, #170), as the
  run row adds it. The kill's figures are the session recap's
  (session_recap.kill_figures): its time over the pull's fights, and the
  boss damage of each fight over their boss dps times (the group's dps,
  said so, for a boss the game does not flag), so the page and its copy
  agree. Under two or more pulls a line
  reads "Pulls: pull 1 (wipe 62%) · pull 2 (kill)", each pull a link to
  its last fight, whose verdict it names (the log can cut a pull in two).
  Each row holds a named anchor (run_anchor), numbered over every run of
  the block in order, where a click on the list's run row opens the page.
  It sits on the count of pulls, plain text: Qt hangs an empty named
  anchor on the first letter of the text after it, and when that text
  was a link, only that letter stayed marked as an anchor, all
  FightView's hover cue and Tab key then took for the link (probed on
  PySide6 6.12.0).
- **What ended the pulls**: the run row's hover widened to every pull of
  the instance, counted once for both (pull_outcome.what_ended): the
  first death of each pull, the killers and the share the bosses dealt,
  and the longest dead, a second or more (a solo player's fight ends as
  they die, which would read "0s"), the TOP of each and an ellipsis when
  there are more. A killer is named after the ability when it is not one
  of the instance's bosses.
- **Trash**, in the copy's words (session_recap.trash_text), and a solo
  dungeon's Misfortunes once: the run's, the same at every pull
  (misfortunes.py).
- **Players**: everyone of the instance but the companions, each once,
  told by handle across its fights, a player the log gives no name
  ("anon") by unit id and class, as the run row's hover tells them apart:
  the class keeps apart two that took one unit id in two logging sessions
  of the instance. Not by role, which the engine guesses fight by fight (a
  healer can read as a damage dealer on trash): role and class are the
  ones most of their fights read, the latest winning a tie. Pulls
  counts the pulls they were in; deaths and time dead count every fight,
  trash too, as each death in a trial costs vitality, so a player's time
  dead can exceed the longest dead line's, which counts the pulls. A
  player's possible build issues go on a line under their row, each
  finding once (by its rule, set, skill and star) in its latest words,
  with the number of their fights it was found in: as a column beside the
  names they were squeezed to a word a line at 200% text, a 12-player
  trial's table 1,522 px tall, 688 with the line (measured; the line
  costs 30-85 px at 100%). A player who died with no row of their own
  (the pane's Also died) is listed with no role. Each name is a link to
  that player's window on Build, on the fight on screen when they have a
  row in it, else their last fight of the instance with one; a player who
  never had a row (their build never reached the log) opens on Deaths, at
  their last death, as the pane's Also died does. The hover names that
  fight ("@x in Nahviintaas, pull 13").

The tables keep their words whole up to 200% text (measured over real
splits): no heading breaks; the figures' columns are as narrow as their
words (FIT) and set apart from the column before (FIGURE), so the boss
and the result keep the width; and every column of the players' table is
as narrow as its words, an empty one taking the rest, so role and class
stay by the name.

Links carry the fight's place in the list the page was drawn from
(index_of), never a path or an entry, as the Recent activity page's do
(gui.activity_render): a link whose fight has left the list does nothing,
and the window says so. A fight index_of does not place gets no link.
Pull links take the link colour; the players' names keep the look of
plain text, as the fight pane's do. Every player's name goes through the
Hide names mask, in its text form in the hover texts.

Nothing here changes an entry: the engine's thread updates delivered
fights in place while a page is drawn (MainWindow._fight_changed), so
their lists are read and counted into new lists and dicts, sorted with
sorted(), never in place.

## The Events tab: a fight's notable events, in order

### src/fight_events.py

*[src/fight_events.py:1](../src/fight_events.py#L1)*

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

### src/event_rows.py

*[src/event_rows.py:1](../src/event_rows.py#L1)*

The Events tab's rows (issue #214): a fight's deaths, the bosses' casts and
health, the big hits on the group, the taunt swaps and the fight's phases,
one row per happening, in time order. Qt-free: the tab draws what this
gives (gui.events_tab).

Design: the Events tab's rows. The rules are the #214 study's, written as
code and measured on six fights (build/surveys/timeline-214-2026-11-11,
design/lists): 5.5 to 16.3 rows a minute by default, never more than 9 in
any ten seconds, so a fight reads as a story rather than a log.

- Deaths are the entry's own recaps (death_recaps), with the death the log
  wrote no line for said so. Deaths to one ability within DEATH_CHAIN_MS
  are one row ("Died x3"). Each return from the dead is a "Back" row with
  how long the player was down and who raised them: a resurrection line
  for the player at most RAISED_BEFORE_MS before the return, else "no line
  says how" (a release and run back writes none). A player dead since an
  earlier pull has no death in this fight: their return says "dead since
  before the pull".
- A boss's casts of one ability, each within BURST_MS of the last, are one
  row ("Hemorrhage x12"), with whom they were aimed at and whether one was
  stopped: by a player ("interrupted by"), or by the boss's own script.
  Rows are keyed by names, not unit ids: a boss the game adds again as a
  new unit is the same boss to a reader.
- A boss's health marks (75, 50 and 25%), the stretches of UNTOUCHED_MS or
  more in which it lost no health, and its death.
- Big hits: BIG_HIT_SHARE of the player's maximum health or more, the part
  a damage shield absorbed and the overkill counted in. One source's hits
  with one ability, each within HIT_CHAIN_MS of the last and all within
  HIT_SPAN_MS, are one row. A lone hit on a player who died to it within
  KILLING_HIT_MS is left to the death's row.
- Taunt swaps: the first taunt on a boss, and a taunt by another player
  than the last one to taunt it. A player taunting again is no row.
- Phases: the map changing, the game ending combat and beginning it again
  in one fight, and a trial's end, at the fight's end.

### src/gui/events_tab.py

*[src/gui/events_tab.py:1](../src/gui/events_tab.py#L1)*

The Events tab (issue #214): the fight selected in the list told as a
table of its notable events, one row per happening in time order (the rows
are event_rows'), with a line that sums it up, the categories to show and
the search of the fight's tabs filtering the rows. The main window's fifth
fight tab, after Deaths.

Design: the Events tab. A table, not a page of rich text like Deaths: a
QTableView over a model reads to a screen reader as rows and cells, the
arrow keys go from row to row, and Enter or a double-click on a death's row
opens that death's recap in the player window (recap_requested, the
(unit id, number) the Deaths tab's names carry). A row of several deaths
(Died x3) opens nothing: it names no one death.

What is shown. The five categories the study chose are on at first
(event_rows.DEFAULT_CATEGORIES: deaths, the bosses, the big hits, the
taunt swaps, the phases), and More holds the three that are off
(event_rows.MORE: a boss's casts at the player holding its taunt, its
auto-attacks, the hits of 30 to 49% of a player's health), which on a
145-second Kyne's Aegis boss fight add 51 rows to its 78. Show picks the
whole fight or its last 60 seconds, where a wipe's story ends. The
choices carry from one fight to the next, as the DPS graph's do, and not
from one run of the app to the next.

The search. The tab bar's search filters the rows to those whose cells
hold its text, case-insensitive, over what the cells show (a hidden name
is its blocks, so a hidden player is not found by name); the field counts
the rows, and Enter goes to the next of them. A table has no text cursor
to move to a match, and a row that matches is shown whole. A search typed
selects its first row, as the text pages put the cursor on the first
match; cleared, the row selected stays and comes into view among the
others.

Around a moment. Show's ± choices keep the rows within 10 or 30 seconds
of a moment: the row selected when the choice is made, named in the count
beside it. The moment stays as the reader picks other rows, so the window
does not slide under them, and from ±10 s to ±30 s; it belongs to its
fight, and another fight goes back to the whole. It is how the other views
open the tab (show_around): a double-click on the DPS graph, the buff
strip's pop-up and a death's Events link in the player window each send
their moment, where the study had a double-click on the strip too: a click
there already opens the pop-up, so the pop-up carries the link. The other
way, Ctrl+G or the link that ends the line under the table marks the row's
moment on the DPS graph (graph_requested), with what happened and no name,
so the mark needs no mask.

Keeping the reader's place. A new fight selects its first death, the
moment a wipe turns on, else its first row. The same fight drawn again (it
changed: a death logged after combat ended, the fight the game had cut in
two going on, Hide names, the text size, the theme) is drawn in place: the
row selected is found again by what it says, its time, what and ability,
not by its place, since rows can come before it, and the scroll is kept.
A category or Show changed keeps the row selected while it is shown, else
takes the first row from its time on.

Hide names. Cells are plain text, so a hidden name is '@' and a block per
character, as in hover text and the DPS graph's legend
(NameMask.text_in): in Who, which can name two players or say '3
players', and in Detail, which names who raised, interrupted or was aimed
at. A screen reader hears 'hidden name' (Qt.AccessibleTextRole), as in the
positions window's table.

Sizes. The rows are as tall as a line of text or an ability icon at the
text size in force (death_render.ICON_PX scaled): a QTableView keeps its
30 px rows at any text size (the positions window measured it). The
filter bar wraps its controls onto more lines as the column narrows (a
flow layout), so at 200% text the tab never sets the column's least width:
its controls take 1,185 px on one line at 200% in Segoe UI (666 at 100%),
where a 1080 px window gives the tabs 705. The Time and What columns are
as wide as the fight's widest cell, Ability and Who too up to a share of
the table, and Detail takes the rest: at 200% text in that column, Detail
had a quarter of the table while Ability and Who took their whole cells. A
cut cell is whole in its hover, and the row selected is whole on the line
under the table, as the study's design has it.

Design: one player's actions on the Events tab (issue #214). Who, first on
the bar, picks Everyone (the rows above) or one of the fight's player
rows (action_rows.players: tanks, healers, then damage dealers, each in
the table's order; companions' casts are not kept), and the table lists
that player's casts with the events that touched them (action_rows has
the rules). It lives here rather than on an eighth tab of the player
window, the maintainer's choice: that window has no search and would need
more than its width at 200% text. The table takes the mode's columns
(ACTION_COLUMNS: Time, Bar, LA, Action, Target, Length, Gap, Detail) and
is named Player actions for a screen reader; a column no row of the
player's fills is hidden (HIDEABLE), judged on all their rows rather than
the ones the filters leave, so columns do not come and go as boxes are
ticked.

The controls keep their meaning for one player. The casts are always
shown; Deaths, Boss, Big hits and Taunt swaps show or hide the player's
events of that kind; Phases is greyed out, its rows (the map, combat begun
again, the trial's end) being context rows (action_rows._context_rows),
which More's Context switch shows with the bosses' health and deaths. More's three kinds are everyone's and greyed
out for one player, and the player's switches (ACTION_SWITCHES: light
attacks as rows, swaps as rows, context) are greyed out for everyone; the
count on More is of the items on that apply. Context rows are italic in
the palette's placeholder colour, the fight around the player rather than
the player's own. Show, the search, the line under the table, Ctrl+G and
Enter on a death's row work on the player's rows as on everyone's. The
marks are words to a screen reader and on the line under the table ('after
a weapon swap', 'after a light attack'), whose two seconds are labelled
('lasted 1.6 s', '1.1 s after the skill before'), as they would read
alike there.

Who changed keeps the reader's moment: the other mode's rows from the
selected row's time on. The player picked carries to the next fight as
the DPS graph's legend ticks do, by legend_key (the handle, or an
anonymous player's zone and unit id): a fight without them shows everyone,
and the next fight with them picks them again. A jump from another view
keeps the mode, but a death's Events link for another player than the one
picked goes back to everyone, whose rows hold that death. The player
window's This player's actions button selects its fight in the list and
opens the tab on the player (show_player), at their first death, else
their first row.

## The Events tab: one player's actions

### src/fight_casts.py

*[src/fight_casts.py:1](../src/fight_casts.py#L1)*

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

### src/action_rows.py

*[src/action_rows.py:1](../src/action_rows.py#L1)*

One player's actions on the Events tab (issue #214): their casts in the
order begun, with the events that touched them between, when the tab's Who
picks a player. Qt-free: the tab draws what this gives (gui.events_tab).

Design: one player's actions, the Events tab's second mode (issue #214).
The study's design (build/surveys/timeline-214-2026-11-11, design/lists,
section 2.2) as the maintainer trimmed it: no judgement marks (no idle
share, no amber gaps, no 'weave' or 'miss'), a gap a plain number, and the
rows below.

- A cast is a row: when it began, its bar slot, the ability, the unit it
  was aimed at, its length and the gap since the skill before. The casts
  are the fight entry's (fight_casts), the Build tab's own count of them.
- Bar: F1 to F5 and FU on the front bar, B1 to B5 and BU on the back, W
  on a werewolf bar the engine rebuilt, for the slot whose skill the cast
  is (casts.slot_holds, as the Build tab puts a count under a slot): a
  skill slotted on both bars reads 'F3/B3', since the log does not say
  which bar was up. Blank for a cast no slot holds.
- A light attack begun LA_FOLD_MS or less before a skill is that skill's
  mark in the LA column rather than a row of its own, and a weapon swap is
  a mark (SWAP_MARK) on the Bar of the next cast begun within
  SWAP_FOLD_MS. A light attack no skill follows so soon, or a swap no cast
  follows, stays a row. The tab's More holds both as rows instead.
- Length: from the cast's BEGIN_CAST to its END_CAST, shown only when the
  log wrote one and it is INSTANT_MS or longer. Over the Kyne's Aegis split
  of 2026-10-11, 15,026 of the 17,641 END_CASTs came in the cast's own
  millisecond and 234 one millisecond later (Swap Weapons, light attacks,
  Bash: casts whose BEGIN_CAST gives no duration), all instants; a
  channelled heavy attack, Claw Fury or Insatiable Hunger lasts 0.5 to 4.5
  s. The BEGIN_CAST's own duration field is never read: it is what the
  cast would take, not what it took.
- Gap: the seconds since the skill before began, for a skill (a cast that
  is none of casts.EXTRA_KINDS: no light or heavy attack, swap, potion
  and the like). A plain number.
- Between the casts, the events that touched the player, from the fight's
  events (fight_events) by their rules (event_rows): their deaths and
  returns; the hits they took of 30% of their maximum health or more,
  chained as the tab's Big hits are, the killing hit left to the death's
  row; the bosses' casts aimed at them, a burst of one ability one row;
  the taunt swaps they were in. Then context rows, drawn muted: the
  bosses' health marks, their stretches with no health lost, a boss's
  death, and the rows the tab's Phases box shows for everyone (the map
  changing, the game ending combat and beginning it again, the trial's
  end), whose box is greyed out for one player.
- No cast for N s: for the player who writes the log alone (the row the
  game flags isLocalPlayer), a stretch of IDLE_MS or more with no cast of
  theirs going on, from the end of a cast (its END_CAST, else its start)
  to the next one's start, the fight's start and end included, less the
  time they were dead (a death to their return, or to the end). The
  client writes every cast of its own player, so a gap there is the
  player's; another player's casts reach the log only while that player
  is near enough to the logging one, so a gap in theirs can be the log's,
  and none is drawn. The row names what the log can say of the stretch:
  big hits the player blocked (a block writes no cast), a boss that lost
  no health then, the map changing, the game ending combat and beginning
  it again; else nothing more.

## Experimental buff timeline

### src/buff_timeline.py

*[src/buff_timeline.py:1](../src/buff_timeline.py#L1)*

Buff/debuff timeline recording (buff-timeline spec).

Records the active intervals of a handful of raid-defining effects with
cast/receive attribution, for the built-in rows of the per-fight timeline
strip (the tracked-effect rules bring the rest, effect_rules). Recording is
always on since the strip became the only view of the rules (issue #25);
the analyzer's track_buff_timeline gate remains for tests.

Interval times are raw log-relative milliseconds; snapshot_fight() clips them
to a fight's [start, end] window and rebases them to fight-relative ms.

### EffectTracker.record

*[src/effect_rules.py:689](../src/effect_rules.py#L689)*

An EFFECT_CHANGED line. *target_kind* is what the engine knows
the target to be: 'self', 'group', 'pet', 'boss', 'enemy' or None.

*source_id* is the caster, kept on the span so a row of the uptime
strip can say who applied it ("" when unknown). Another caster
refreshing the effect ends one span and starts the next, so each
span is credited to whoever last applied it; the spans abut, and
every measurement takes their union, so no number changes.

A ``dots`` rule's spans are kept per caster (each wearer's Touch of
Z'en is their own debuff), and while one is held every effect a
caster has on a hostile is followed too (_record_effect).

### src/effect_summary.py

*[src/effect_summary.py:1](../src/effect_summary.py#L1)*

Who applied an effect and who had it, over a whole fight (issue #19).

A row of the uptime strip is a list of intervals, each naming its caster
('source') and receiver ('target'): the built-in rows from the buff
timeline recorder, the tracked rows from the effect tracker. Hovering the
strip shows the intervals at one instant; summarise() adds them up over
the fight for the pop-up a click on the row opens.

Every figure is a union of intervals as a share of the fight, the rule the
row's own uptime uses (timeline_strip.uptime_pct), so the receivers' lines
and the casters' lines each union back to the headline:

- a caster's *uptime* is the time any of their intervals was up, and their
  *sole* time the part of it no other caster's interval covered; two
  supports keeping Major Courage up between them show the overlap in the
  gap between the two;
- a receiver's *uptime* is the time the effect was on that unit;
- *spans* counts intervals, not casts: the recorders merge a recast that
  follows a fade within moments into the span before it.

An interval without a caster (an old saved fight, or a proc the log writes
without a unit) is counted under UNKNOWN_SOURCE rather than dropped.

### paint_sparse_span

*[src/gui/timeline_strip.py:240](../src/gui/timeline_strip.py#L240)*

Paint one span of a group buff that reached only one or two receivers
(issue #45): the effect's colour at SPARSE_BASE_ALPHA over the row's
full height, under a cross-hatch of the full colour, so the span is
unbroken along the time axis and textured across it.

Up to 0.13.1 such a span was a dotted line down the row's middle, and a
row of dots is exactly what a solid bar looks like when the effect
comes and goes every few seconds: at a glance, up the whole time on
one person read as up half the time on everyone, and the two call for
different fixes (whom the buff reaches against how long it lasts). A
fill with no gaps keeps up reading as up; the hatch says not the whole
group. The lines are drawn here rather than with one of Qt's pattern
brushes so that their spacing suits a ten-pixel row (a step no larger
than the row's height puts a line through every column) and so that
they fall on a grid anchored at the track's left edge, the same
wherever a span starts. The caller paints the union of the row's
intervals, one call per merged span, so overlapping receivers do not
double the translucent base and abutting spans show no seam.

## Split log retention: zipping old splits and moving older ones to the Recycle Bin

### src/split_retention.py

*[src/split_retention.py:1](../src/split_retention.py#L1)*

Split log retention: zip split logs older than N weeks (issue #86) and
move those older than M weeks to the Recycle Bin (issue #87).

Which files. Only the splitter's own names are touched:
``YYMMDDHHMMSS-<Zone-Name>[-vet][-N].log`` and the same with ``.zip``
added. The split folder defaults to the log's folder, which also holds
Encounter.log and the archiver's ``Encounter-*.zip``, and Chris's split
folder holds ``*-report.txt`` files another tool writes; none of those
match. ``-temp.log`` (a split still waiting for its zone) never matches,
subfolders are never entered, and symbolic links are skipped. That makes a
``keep`` folder inside the split folder a place where nothing is ever
zipped; the job creates it so it is there to use.

How old. A split's age runs from the later of the session stamp in its name
and its modification time. On the 899 splits in Chris's folder
(2026-10-27), 433 had a modification time more than two days off their
stamp, because the splitter wrote some sessions out again long after they
were played (issue #85). The later of the two never makes a file look older
than it is, and a session that stays open for days, with an old stamp and a
file still growing, stays young.

The latest session. The split of the live log's newest session (its last
BEGIN_LOG) is never touched: it may be the file the splitter has open, and
it is the one session the app replays at every start, so deleting its
split would only have it written out again. The newest session in the
folder is spared too: it is almost always the same one, and Settings can
find it without reading the log, so its preview counts what a run does.

Deleting (issue #87) moves files to the Recycle Bin (recycle_bin), never
deletes outright; a file the bin cannot take is left and reported. M must
be more than N while zipping is on, so a split is zipped before it can be
deleted; settings_from_config holds to that even for a hand-edited config.
A run deletes first and zips what is left, since zipping a file about to
be deleted is wasted work. Settings asks before saving a change that
deletes: turning it on, lowering M, or pointing it at another folder; the
daily run deletes only within what was confirmed and asks nothing.

Zipped splits are still splits. ``<stem>.log.zip`` holds one member,
``<stem>.log``, so the original name stays visible and a ``*.zip`` pattern
cannot mix it up with the archives. The splitter's checks for "this session
already has a split" (LogSplitter._scan_existing_splits and
LogFileMonitor._session_split_exists) accept the zipped form, indexed by
the member's size; without that, zipping the newest split of someone who
had not played for N weeks would have it written out again at the next
start, and zipped again under a ``-1`` name.

Writing safely, as the log archiver does: the zip is written to
``.partial``, read back in full (CRC and size), given its final name, and
only then is the log removed, so an interrupted run leaves the log or a
verified zip, never neither. A ``.partial`` left by an interrupted run is
removed at the start of the next. The zip and its member keep the log's
modification time. A zip of the same name that already exists is either
the same log (the log is then removed as a copy) or a different one (the
log is left and reported).

What it saves. Deflate at level 6 brings a split to about 6% of its size
(a 95 MB Hel Ra split to 6.0 MB in 1.0 s, a 573 MB Dreadsail split to
34.8 MB in 5.7 s, both read back in under 2 s). On a folder Windows
already compresses (Chris's: 105 GB stored in 32 GB) the saving is
smaller: about 26 GB there rather than 92.

When. At startup and once a day while the app is open, on a thread of its
own (RetentionRunner), one file at a time with a check for cancel between
chunks: the first run over a large folder takes minutes, and the engine
thread that polls the live log must not wait for it.

### src/recycle_bin.py

*[src/recycle_bin.py:1](../src/recycle_bin.py#L1)*

Moving a file to the Recycle Bin (the trash on Linux and macOS), never
deleting it outright (issue #87).

Why not send2trash on Windows. Both its Windows backends ask the shell to
delete with "allow undo" and "no confirmation". When the Recycle Bin cannot
take a file (a network or removable drive, the bin turned off for the
drive, a file larger than the bin's limit), Windows then deletes it
outright without a word; its pywin32 backend's progress sink returns
E_FAIL in that case, but its own comment says the delete goes ahead. So on
Windows this module:

1. Checks the bin can take the file: a fixed local drive, no
   NoRecycleFiles policy, the drive's bin not set to delete at once
   (NukeOnDelete), and the file no larger than the drive's bin limit
   (MaxCapacity in MB, under HKCU\...\Explorer\BitBucket\Volume\{guid};
   a RecycleBinSize policy, a percentage of the drive, wins; a drive with
   neither gets Windows' default of 5%). A file that fails the check is
   left where it is and reported.
2. Asks the shell (SHFileOperationW) with FOF_WANTNUKEWARNING as well, so
   should the check ever be wrong, Windows asks before deleting outright
   rather than doing it.

Elsewhere send2trash moves the file to the freedesktop trash (Linux) or the
Finder's (macOS); both fail rather than delete outright when there is no
trash for the file.

### src/log_open.py

*[src/log_open.py:1](../src/log_open.py#L1)*

Opening a log for review: a plain log, a split the retention job zipped
(``<stem>.log.zip``, issue #86) or an archive the log archiver wrote
(``Encounter-*.zip``).

A zip is read as a stream through its member, never extracted to disk or
read whole into memory: an archive can hold a log of more than a gigabyte.
The size reported for progress is the member's own, since the zip's is
about a sixteenth of it. A zip is recognised by its content, not its name.

## Split files for an instance: from a fight to its session's split

### src/session_splits.py

*[src/session_splits.py:1](../src/session_splits.py#L1)*

The split files behind an instance (issue #194): for each logging session
a block of the fight list holds (fight_blocks), the files in the split
folder that hold it, for the Instance tab's links and the result strip's,
so a run can be handed to a log tool without a search through a folder of
hundreds of splits. No Qt.

By the session's stamp. The engine keeps on each fight the stamp its
session's split is named by (FightHistoryEntry.session_stamp): the
session's BEGIN_LOG time to the second, ``YYMMDDHHMMSS`` in local time,
from the one function the splitter names its files with
(split_retention.session_stamp). It is set as the fight is built, before
the fight is sent, and carried onto a fight the game cut in two with its
other slots. So a fight finds its file by name. A guess from the fights'
own clock times could pick a neighbouring session, since a session starts
before its first fight and can run on into the next instance. The zone in
the file's name is never compared: the splitter names a session after the
zone of its first fight, and of 633 fights replayed from 34 of Chris's
splits (2026-11-09), 39 were in another zone than their file's name, all
in two files (Lucent Citadel fights in a ``…-Maw-of-Lorkhaj-vet`` split,
The Cauldron in a ``…-Volenfell-vet`` one).

Per stamp, in order. A block can span several sessions (a new BEGIN_LOG
mid-run: a relog, a crash, the log turned off and on; by issue #196's
survey 36 of the 366 blocks in that folder span 2 to 5 splits), and one
session can hold several blocks (two dungeons in one sitting). So
splits_for takes the stamps of a block's fights, one per fight, and gives
one SessionSplits per stamp, in the order the fights first carry it.

Several files for one session. A session has one split now: the ``-N``
files are copies the splitter wrote before 0.19.0 (issue #85), and since
then a file gets a suffix only when the file of its name begins with
another session's lines (a second session in the same second). In that
folder 10 sessions still have more than one file, 32 files of which 30
are suffixed, once the byte-identical copies went to the Recycle Bin, and
each of the 22 smaller ones is a byte prefix of its session's largest: a
copy cut short when an earlier run stopped mid-session. In 2 of the 10
the largest is a ``-N`` file, so the plain name would offer a cut copy.
The files therefore come largest first, a zipped split (issue #86) by the
size of the log inside it; at equal sizes the plain log before a zip, the
split folder before its keep folder, and the plain name before ``-1``
before ``-2``. SessionSplits.best is the first, and the rest stay listed.
The fight history's backfill reads such a session the same way round,
its longest log last (fight_index).

Where. The split folder's own files (split_retention.scan_splits: the
splitter's names only, plain or zipped, never ``-temp.log``) and those of
its keep folder, where split retention never zips or deletes, so a split
moved there to keep it is still found. No other subfolder is entered.

Missing or not known. A stamp no file carries is missing: splitting was
off for that session or wrote to another folder, or the file was moved,
deleted, or sent to the Recycle Bin by split retention. A fight with no
stamp ('') is from a session whose BEGIN_LOG the engine never saw (the app
attached to a session that began beyond its 2 GB lookback, or a reviewed
log opens mid-session): it is not known, and nothing is looked for.

The clock. The stamp is local wall-clock time, by this machine's time zone
with that zone's rules for the instant, so daylight saving shifts
nothing: in Chris's folder each of the 408 splits holds one session, its
BEGIN_LOG the first line, and the stamp worked out from that line is the
file's own in all 408, 250 at UTC+10 and 158 at UTC+11. A split written
under another time zone (the machine's was changed, or the folder came
from another machine) carries a name this machine would not give the same
BEGIN_LOG, so its session shows as missing. The hour repeated as daylight
saving ends gives two instants one stamp, so two sessions begun an hour
apart in it would each be offered both files; no session in that folder
began before 7 a.m. A session that runs past midnight keeps the day it
began; none in that folder did (the latest ended at 23:46).

### split_lines_html

*[src/gui/fight_render.py:213](../src/gui/fight_render.py#L213)*

Design: the split logs beside a run (issue #194). The result strip
of the fight that completed a run, and the Instance tab under its
result, list the split logs that hold the run's logging sessions
(session_splits), so a run can be handed to a log tool: a line each
from *files*, a list of (label, path or None, note). A file shows with
two links, open folder, which opens its folder with the file selected,
and copy path, which puts its full path on the clipboard; they carry its
place in *files*, never the path (#191), and the window keeps the list
it drew the page with. A note says why there is no file: split logs
off (the default), the session's file missing, the session not known.
Under Hide names (*hide_paths*) a file shows by its name alone, since
its folder names the Windows user; the copy is still the full path, as
it goes to a file dialog, not a post. A review lists the reviewed file
instead. The lines name whole logging sessions, the safe unit to join
logs by (#195).

## The GUI and the engine thread

### src/gui/engine_worker.py

*[src/gui/engine_worker.py:1](../src/gui/engine_worker.py#L1)*

Engine worker: runs the analysis engine on a QThread and bridges
AnalyzerListener callbacks to Qt signals (queued to the UI thread).

Engine modules never import Qt; this adapter is the only crossing point.

Design: the worker is a Python-created QObject, so it is freed on the UI
thread and never by Python's garbage collector, which frees whatever is
garbage on whichever thread happens to be allocating. As the worker's thread
finishes, QThread.finished calls leave_thread on that thread (a direct
connection): the timers stop and the worker moves itself to the UI thread,
since only the thread an object lives in may move it. The window then
deletes it there (MainWindow._discard_worker). The listener holds the worker
weakly, so a worker nobody holds is freed at once.

Until issue #18 the window tried to pull the worker over from the UI thread
after the thread had ended. Qt refuses that ("Cannot move to target thread",
printed at every close), so the deletion went to a thread that would never
run it. The listener also held the worker in a reference cycle, so only the
garbage collector could free it. In the test suite, where every GUI test
leaves windows and workers behind, a collection was seen running on an
engine thread; one that found GUI objects there would free them off the UI
thread, which is how Settings crashed in 0.6.x.

### MainWindow._on_monitoring_restarting

*[src/gui/main_window.py:1289](../src/gui/main_window.py#L1289)*

The engine has begun the restart Settings asked for. Everything
it sent before this belonged to the analyzer being replaced, so the
history is cleared now rather than when Save was pressed: a replay
still running at that moment went on filling a list cleared too
early, and its fights showed above the new analyzer's.

The replay comes back to the fight the reader was on (issue #196):
the clear used to leave a reader of an older fight with nothing
selected, under a page whose links all returned early for want of a
current fight. The new analyzer builds new entries, so the fight is
known again by its key (fight_blocks.fight_key), kept here, and the
pane says the session is being replayed in place of the stale page.
Following the live log is held off until monitoring_started, which
the engine sends after the replayed fights: the fight with that key
is selected as it arrives, unless the reader has picked one (the
emptied list picks none itself when it takes the focus,
FightList.focusInEvent, and End goes to the newest so far,
FightList.moveCursor), and no other fight is. Without the hold,
_show_fight would start following once the fight came back as the
newest so far, and every later fight of the replay would be
selected in turn. A restart that finds no log waits for it
(waiting_for_log), and the hold lasts until the monitoring_started
sent once the log appears and is read; the first fight read from it
puts the replay's line back in place of the waiting page. At
monitoring_started (_end_replay) the fight on screen stays, the one
that came back or the reader's pick; with none the newest is
selected, the list having followed the live log or the fight not
having come back. The replay reads only the log's latest logging
session (LogFileMonitor._load_latest_session), so a fight of an
earlier session the app tailed is gone, as is every fight when the
log is another or was replaced since. Following is then
_show_fight's rule again for the fight selected: the newest
follows, an older fight does not.

A review keeps its list and its selection, and the hold starts
under it all the same, with no fight to come back to: Back to live
during the replay lists the fights so far, none selected, under the
replay's line, and the newest is selected once the replay is in
(_exit_review). Without the hold, Back to live followed the live
log and selected each fight of the replay in turn. While the engine
waits for a log the restart did not find (_log_missing, cleared
here and set again by waiting_for_log), Back to live with no fight
listed draws the waiting page instead: nothing is replayed until
the log appears.

The windows' fights are known again by their keys too
(_rebind_windows puts each window on the replayed copy): the player
window's with the player's handle, which the copy must give again
under the same unit id; the positions window's by the key alone,
its units being the fight's (issue #214). A replay of the same log
gives the same locator, so that window keeps the states it read,
and the rows, numbers and roles it draws come from the new entry
(companion accrual, say, changes the rows). A window on a reviewed
fight, which no replay builds again, keeps it.

### Qt objects are freed on the UI thread

*[src/gui/main_window.py:3137](../src/gui/main_window.py#L3137)*

Delete the closed dialog here, on the UI thread, rather than leave it to Python's garbage collector, which frees whatever is garbage on whichever thread is allocating at the time. That was the engine thread replaying the log after the restart, and freeing the dialog's Qt objects there aborted the app (settings crash, 0.6.7)

### MainWindow._fight_changed

*[src/gui/main_window.py:1112](../src/gui/main_window.py#L1112)*

A delivered fight changed in place (a fight update from the
engine, a score banner attached): its history line is rewritten, the
pane redrawn if the fight is on screen, and every open window on that
fight redrawn, each keeping its place, the windows with the Hide
names mask made afresh from the fight, since a fight the game cut in
two can bring players its first part did not have (issue #196). A
hidden window, or one on another fight, is left alone: opening it
draws the fight anew.

A window tells its fight by identity (window.entry is entry), with
no key of time, zone or boss, because the engine never sends a
changed fight as a new object: it changes the one the frontends
already hold. A late death replaces that entry's deaths and recaps,
a fight the game cut in two has every slot of the finished entry
copied onto it, the run's result (trial_result, its pull marked won)
is written into it when END_TRIAL follows the fight, a mastery found
later in the session and a later pull's reading of its outcome are
written into it, and the banner is attached to it here. The engine
writes on its own thread and then sends fight_updated, and the
windows read the entry without a lock, as the pane and the run rows
do: safe while each write replaces a value, a slot or a key the
entry was built with. So the GUI writes nothing into an entry, a
pull, a player row or a recap (banner_path aside), and orders with
sorted() and new dicts, never .sort() or an added key: CPython
empties a list while it sorts it, so an engine write built from that
list meanwhile would lose its items.

The positions window (issue #214) draws the fight's states, read
again from disk by its locator, and is asked for a new read only
when the update brought a new locator: a fight the game cut in two
that went on is the one update that replaces it (the finished
entry's slots copied onto the delivered one, its end later). A late
death, a fought-on rebuild, a mastery found later, END_TRIAL and a
banner leave the same locator object, and the window redraws its
numbers, roles and death marks from the entry it holds: reading
again on every update would have read 158 times in 172 for nothing
(the replay design's engineering critique, R9). The window waits
for the read it asked for and drops the answers to earlier ones; a
hidden window is asked for nothing, and its next link reads what it
lacks.

### Steps after the page is laid out

*[src/gui/fight_view.py:174](../src/gui/fight_view.py#L174)*

restore_scroll and open_at_anchor put the page where it should be now, and again in a step on the next pass of the event loop. Qt lays a page out in parts, the first in setHtml and the rest on its timer ticks after that step, and until it is done the bar's range is an estimate from the part laid out, short of the page's or past it. A scroll put back stops at the estimate, so a build window redrawn at or near its end landed up to 92 px short of where it was (97 of 940 redraws of real build pages, issue #196). So the place is held for HOLD_MS: each change of the bar's range puts the page there again, until it gets there, and the reader moving the page, with the wheel, a key, the bar, Tab or the in-fight search, ends the hold at once, so the page is never taken back from under them (release_place). The step runs on a single-shot timer the view owns, connected to the view's own method: deleted with the view, the timer never fires at a dead one, and the connection keeps nothing alive. The forms used before, QTimer.singleShot(0, ...) with a bound method (restore_scroll) or with a lambda holding the window (the build window's anchor scroll), raised "Internal C++ object already deleted" when the view was deleted first, and kept the view's Python wrapper, and the lambda the window's too, alive until then; QTimer.singleShot(0, view, method) does not raise but keeps the method, and so the wrapper, alive (all probed on PySide6 6.12.0). A new page drops the step and the hold of the one it replaces. A redraw of the page while the step is to run or the place is held, a second fight update in the same pass say, puts the page where they were to put it, not where its bar is meanwhile (keeping_place).

### FightView.keeping_place

*[src/gui/fight_view.py:398](../src/gui/fight_view.py#L398)*

Redraw the page the reader is looking at inside the with block,
and put it back where it was: at the bar's position, or, while the
step after the last drawing is still to run or its place is held,
where they were to put it (its scroll or its anchor), since the bar
is not there yet (see __init__). The with block is given where the
text cursor was, for the in-fight search to find its place among its
matches before the page is drawn again (MainWindow._search_place).

A link the reader had reached with Tab has Tab's focus again, known
by its href and its place among the page's links with that href (an
ESO-Hub set link is on every player who wears the set, and a
player's own links move when the fight ranks them anew), or none
when the page no longer has it. Selecting it with setTextCursor
would paint it as selected text, in the palette's highlight, where
Tab draws a dotted frame round it; so Tab's own step is taken, which
frames it: from the link before it, selected as Tab selects it, or,
for the page's first link, from no selection, where Tab starts at
the page's start. Never from a selection of the character before
it: QTextCursor widens a selection that crosses into a table over
the whole table, and a bar's first ability begins a table's first
cell (the build card's in the pane, its bar's own in the build
window), so Tab's search went on from the table's end, to the next
link after it. The step is QTextBrowser.focusNextPrevChild, which
moves the focus on to the next widget when its search finds no
link, as it did then with none after the table. It cannot now: the
step is taken only for a link the page has, with the links reachable
from the keyboard, and from where that link is the next one the
search finds, since _links reads the page's links as the search does
(issue #196).

A link the reader could see stays where they saw it on the screen
(keep_link_at), and the page moves under it: a fight ranking its
player anew moves the link down the page, and Hide names moves it
too. Kept by the bar's position, the link was often scrolled out of
sight, its focus frame with it, and Enter opened a link the reader
could not see (issue #199). A new text size moves it before the page
is redrawn, so MainWindow.set_text_size notes it first. A link the
reader has scrolled out of view leaves the page at their scroll, as
does a page with no link reached.

## Reviews: a thread of their own, and where a large log is cut

### src/review_load.py

*[src/review_load.py:1](../src/review_load.py#L1)*

Replaying a log for review (issue #107): the engine side of "Open log for
review…", with no Qt in it, so it runs on a thread of its own while live
monitoring keeps its poll.

A large log is first outlined: one pass over the line heads that finds each
session's start (``BEGIN_LOG``) and counts its fights (``BEGIN_COMBAT``),
so the window can offer the whole log or only its most recent sessions.
The cut is always at a session start. Starting in the middle of a session
was measured and rejected: the roster lines alone do not carry what the
engine learns from the rest of the session (who owns which companion and
pet), and on a Dreadsail Reef split every one of the last 18 fights came
out different. A replay from a ``BEGIN_LOG`` matched a replay of the whole
file in 75 of 75 fights (once champion points followed the log).

Lines before the first session read are skipped unparsed, so a cut log
costs a pass over its head plus the engine's time for the rest. The engine
runs at about 10 MB/s on the maintainer's machine, which the time estimate
uses.

### src/gui/review_runner.py

*[src/gui/review_runner.py:1](../src/gui/review_runner.py#L1)*

A review on a thread of its own (issue #107). Until 0.21 a review ran on
the engine thread, whose poll timer then waited for it: a month-sized log
took 8.6 minutes with no live fights shown. Now the engine polls on while a
review replays through an analyzer of its own.

The thread holds no Qt object. It reports through *notify*, which the
window turns into a signal on an object living on the UI thread (as split
retention does), so nothing Qt is created or freed here; the analyzer and
its fights are plain Python. The settings are a snapshot taken when the
review starts, since Settings may change them meanwhile.

## Re-reading one fight: where its lines are in the log

### src/fight_locator.py

*[src/fight_locator.py:1](../src/fight_locator.py#L1)*

Where a fight's lines are in its log, and who its units are (issue #214):
the locator the engine keeps on each fight's entry, by which a view
re-reads that one fight from disk (fight_reread) instead of the engine
holding every unit's place for the whole session.

Design: Byte offsets from the session's BEGIN_LOG line. The locator holds
the offsets of the fight's BEGIN_COMBAT and END_COMBAT lines and of its
zone's ZONE_CHANGED line, each counted in bytes from the first byte of the
session's BEGIN_LOG line, with that line's own offset in the file the
engine read and its Unix milliseconds. Counted from the session, an offset
is the same number in the live log, in the session's split and in a zipped
split's member: a split written since 0.19.0 is its session's bytes (6 of 6
sessions of the live log byte-identical to their splits, 116 MB down to
11 MB), and a zip's member is a byte copy of the split. Every reader that
feeds the engine therefore reads bytes and says where each line starts
(``ESOLogAnalyzer.line_offset``): the live tail, the attach and Settings-save
replay, the review of a plain or zipped log, and the roster sweep.
Characters are not bytes: over the 411 split logs (35 GiB, 213.5 million
lines, every one ending CRLF) text mode falls 213,527,919 characters short
of the bytes, one per CRLF plus 1,257 for the multibyte letters of player
names. Reading bytes costs nothing: whole engine passes over a Rockgrove
and a Kyne's Aegis split ran 0.1% and 0.4% faster than in text, with the
same fights, and the counting itself is 0.03 µs a line. The live tail
holds back a last line the game has not finished writing, so every line
reaches the engine once, whole, with its offset; so do the attach replay
and the roster sweep at the point where they hand over to the tail. Read
in text, a poll that landed inside a line handed the parser two broken
lines, and in a test a fight was lost that way. In all 8,932 fights of the
391 split logs (35.8 GB), 448 of them fights the game cut in two or more,
the BEGIN_LOG, ZONE_CHANGED, BEGIN_COMBAT and END_COMBAT lines were at
their recorded offsets, and every other field of every entry was as
before. Ten splits zipped as retention zips them gave the same locators
(186 fights), and so did two logs of three sessions each, attached to and
tailed in about 1,180 polls each, nine in ten of them ending inside a line;
the splits that tail wrote were byte-identical to their sessions.

A split written before 0.19.0 lacks the lines the parser rejects (a
cancelled cast, an OBJECT unit): a median 7.7 KB before a fight's
BEGIN_COMBAT, so an offset taken from the live log lands late in it. So
the reader checks the lines before trusting the offsets: the line at the
session's base is a BEGIN_LOG with the session's Unix milliseconds, and the
line at the BEGIN_COMBAT offset is ``<start ms>,BEGIN_COMBAT``; when either
fails it finds the fight by its times within the session.

The fight's times are its BEGIN_COMBAT and END_COMBAT lines' (start_ms,
end_ms), taken as the entry is built, where every path that builds one has
restored the fight's own start. Read at any later moment the encounter's
start is not the fight's: a combat event after END_COMBAT sets the
encounter in combat again and moves it, which at the next BEGIN_COMBAT had
happened in 1,130 of 1,152 encounters, by a median of 16 s and up to 441 s.

The range a view reads is not stored: from LEAD_MS before BEGIN_COMBAT
(the moments the opener and the group's waiting hits read, fight_opener,
waiting_hits) to TAIL_MS after END_COMBAT (the late-death grace). The
reader finds its first line by time, reading back from the BEGIN_COMBAT
line, never past the zone's ZONE_CHANGED line (unit ids start over there)
or the session's BEGIN_LOG; over the 411 splits those 10 s held a median
128 KB and at most 2.0 MB. It reads on past END_COMBAT to the first line
after the tail, and stops at the next BEGIN_COMBAT, ZONE_CHANGED, BEGIN_LOG
or END_LOG: over the 391 splits the next fight's BEGIN_COMBAT came within
the tail in 801 of 8,932 fights, and 3,301 lead-ins reached back over the
fight before. The group fighting on after END_COMBAT (#162, waiting_hits)
is not in the range: that rebuild takes only the damage figures and keeps
the locator, so the seconds the DPS graph shows past the fight's end are
outside the view, as the fight's clock, deaths and recaps are.

The map. The log's coordinates are fractions of the map last named by a
MAP_CHANGED line, and a lead-in held one in 980 of 8,932 fights (11%), so
the locator carries the map in force at the lead-in's first line
(map_at_lead), and the reader switches maps at each MAP_CHANGED line in the
file's order. MAP_CHANGED lines are kept per zone (MAPS_KEPT).

The unit table is the engine's identity of the fight's units, frozen as the
entry is built, so a re-read never works out who a unit is. A player's row
holds every unit id they had in the fight: their record's, the ids they came
back on (presence.py, rule 3) and the ids they were known by as BEGIN_COMBAT
redid the roster. A companion's row holds every unit id the companion had,
under its row's key and the name the fight shows (companions.shown_name,
never the log's). A pet keeps its owner after its UNIT_REMOVED or its owner
field dropping to 0, which the engine's own map of pets forgets: a table
taken from that map at the fight's end gave the wrong owner on 1.52% of
the unit states in the fights' ranges, in 206 of 545 fights; keeping each
pet's last owner left 0.011%. Monsters, NPCs and pets are listed when they
were in the zone during the range; each row's window (since_ms, until_ms,
its UNIT_ADDED and UNIT_REMOVED, a player's arrival and departure) tells
apart a unit id handed to another unit, the latest arrival winning. Units the
log never announced in the zone (anchors, hazards) and objects, whose
UNIT_ADDED the parser rejects, are not in it: over one split of each of 21
zones, 99.04% of the 7.7 million unit states in the fights' ranges were of
a unit in the table, every state of a unit in it was, and the reader reads
the rest as unknown units. As tuples the locator is a median 29 KB for a
12-player boss fight (p90 74 KB), 1.4 to 1.6 MB for three hours of trials.

### src/fight_reread.py

*[src/fight_reread.py:1](../src/fight_reread.py#L1)*

Re-reading one fight's unit states from disk (issue #214), for a view that
shows the fight paused at a moment: where everyone stood, with their health
and pools. The engine keeps no unit's place for a whole session. It keeps a
locator on each fight's entry (fight_locator), and this module reads that
fight's lines back by it. No Qt, and the engine is never imported.

What it reads. Unit states, and the maps they are drawn on. A state is the
ten fields the log writes for a unit: its id, health, magicka, stamina,
ultimate, werewolf and shield, then its place and heading. They are read
where the engine reads them: the source and target of COMBAT_EVENT,
EFFECT_CHANGED and BEGIN_CAST, and HEALTH_REGEN's unit. Three are skipped.
A target of ``*`` is the source again. Unit id 0 is no unit. The 1/1
placeholder (health 1 of 1 at place 0, 0) is what the log writes for a unit
it knows nothing about. A member far off the map, in another zone or
instance, is kept as written; on_map tells such a place. Casts are not
read. The game hands a cast's track id on to later casts, so a second count
would disagree with the engine's, and the cast rule is the casts step's.

The range. It runs from LEAD_MS before BEGIN_COMBAT to TAIL_MS after
END_COMBAT: the opener's and the waiting hits' window before the fight and
the late-death grace after it (fight_locator). The group fighting on after
END_COMBAT (#162) is not in it, as the fight's clock, deaths and recaps
are not. The locator stores no range. The reader reads back from
the BEGIN_COMBAT line to the first line whose time is start - LEAD_MS or
later. It never reads past the zone's ZONE_CHANGED line, where unit ids
start over, or the session's BEGIN_LOG, and a ZONE_CHANGED met in the
lead-in drops what was read before it. It reads on past END_COMBAT to the
first line later than end + TAIL_MS. It stops early at the next
BEGIN_COMBAT, ZONE_CHANGED, BEGIN_LOG or END_LOG: the next fight's
BEGIN_COMBAT came within the tail in 801 of the 8,932 fights of the 391
split logs. A fight the game
cut in two is read whole, its first END_COMBAT and second BEGIN_COMBAT
included. When the bytes end first, as in a live log, the read ends there
with tail_seen False, and a last line still being written is not read.

Finding and checking the bytes. The places are tried in order: the
reviewed file and the session's splits by its stamp (session_splits),
plain before zipped (a zip's member streams from its start and cannot
seek); the live log among the plain files when the line at the engine's
hint, or its first line, is the session's BEGIN_LOG, else after them all,
since it would be searched back whole; then the archives. In each the
session's BEGIN_LOG is found: at offset 0 in
a split, at the engine's hint in the live log, else by a search back from
the end for its exact token ``,BEGIN_LOG,<unix ms>,``. The offsets are then
checked before they are trusted. That line must be the session's BEGIN_LOG,
the line at the BEGIN_COMBAT offset must be exactly ``<start>,BEGIN_COMBAT``,
and the line at the zone offset a ZONE_CHANGED. A split written before
0.19.0 lacks the lines the parser rejects, a median 7.7 KB before a fight,
so offsets from the live log land late in it. When no place passes, each
place holding the session is searched by time: a bisection on line times
in a plain file (times never go back within a session), one pass over a
zip's member. A fight with no BEGIN_COMBAT line, in a session that opens
mid-fight, is always found by time. found_by says which way it went.

Who is who. Identity is the engine's, frozen in the locator's unit table;
nothing here works it out again. A unit id at a time names the table row
that lists the id and whose window, since_ms to until_ms with both ends
in, holds the time. The latest arrival wins, so an id the game handed to a
new unit names each unit in turn. All of a row's ids make one track, so a
player back on a new unit id stays one track. An id that names no row at
that time gets an unknown track of its own: anchors, hazards, objects whose
UNIT_ADDED the parser rejects.

Frames. The log's coordinates are fractions of the map last named by a
MAP_CHANGED line. Frame 0 is the map the locator names for the lead-in's
start, and each MAP_CHANGED line in the range starts the next frame, in
file order: states written after the line, even in its millisecond, are of
the new map.

What it keeps. Each track keeps one state a millisecond, the last line of
the millisecond winning (a damage line shows the health after its own
hit), and drops a state equal to the one before, keeping instead when it
was last written (seen). A unit standing still at full pools is written
again and again unchanged, so the time of its state is not when the log
last said where it was: over seven boss fights of Kyne's Aegis and
Sanity's Edge, 25 to 88% of the player-seconds whose state was over a
second old had a line for that player within the second, and every one in
Sanity's Edge's lead-ins did. So a moment's age counts from seen, and a
unit is stale only when no line has written it. The states are packed in
columns: time, place, heading, health, magicka and stamina with their
maxima, ultimate, shield, frame and seen. Each column of all tracks is one
immutable bytes object read through read-only memoryviews, so a result is
cheap to hold and safe to hand from the reading thread to the UI.

Measured on the 21-split sample (846 MB, 545 fights;
scripts/check_fight_reread.py). The offsets held in all 545 fights, and
with every offset spoiled by 13 bytes all 545 were found by time with
identical states. Of 17,167 tracks built from the engine's own fields and
identity at each line, 17,154 were byte-identical. The other 13, in 8
fights, held 49 states of companions the engine had not yet linked to their
owner, which the table already names. Of 7.71 million state occurrences
the table named the engine's unit for all but those 49, and the owner for
all but 824 (0.011%): pets after their owner field dropped to 0, which the
table keeps and the engine forgets. A state costs 48 bytes, against 441 as
tuples; a 12-player boss fight's result is a median 609 KB, 2.2 MB at most
(46,368 states). Every fight of three splits zipped as split retention
zips them read the same from the zip, by offset and by time.

Read alone from its split, a 12-player boss fight took a median 95 ms by
offset (p90 229 ms, at most 402 ms for a 316 s Lord Falgravn kill) and 145
ms by time. That kill took 396 ms from a two-session live log with the
hint, 455 ms without it, and 643 ms from its zip, whose member streams from
its start to the fight 92 MB in. Reading in 4 MB chunks needs at most 19 MB
from a plain file and 27 MB from a zip. RereadRunner reads on a thread of
its own, not the review's, whose one job can run for minutes, and a cancel
is seen between chunks.

## Positions: a moment held still, and played back

### src/gui/positions_window.py

*[src/gui/positions_window.py:1](../src/gui/positions_window.py#L1)*

The positions window (issue #214): one fight at a moment, where everyone
stood, with their health, opened from a death (and later from an event) of
the fight, held still or played back (#232).

Design: One window, re-used, beside the main window, as the player window
is (a QDialog child of it, never deleted before it, hidden by Esc): it
keeps the fight it was opened for while the list moves on, and it has
room the main window's tabs do not. Its parts, top to bottom: the fight
and the moment ('Lord Falgravn · Kyne's Aegis VET · Kill · 1:50.0 of
5:16'), Show in list; each boss's health at the moment; the canvas
(positions_canvas) beside a table of the same units in a splitter, the
line under the canvas naming who is not drawn ('Not on this map: 6, 11');
the controls (previous death, a second back, the moment's clock, a second
on, next death, Show); and Play, the speed and the scrub bar, a row of
their own (the controls' row had no room left at 200% text). Decided for
#214: players, bosses and adds drawn, pets, companions, unannounced and
other units each one toggle away in Show, no casts yet; #232 added
playback (below).

What it draws comes from two places. The fight entry gives the numbers,
the roles and the deaths: a player's number is the place of their row in
the fight table (companion rows skipped), worked out afresh each time the
fight changes in place, since the engine can re-rank the rows; a death's
moment is the locator's start plus the recap's time into the fight, in
the log's own clock (ms since BEGIN_LOG). The states come from re-reading
the fight from disk (fight_reread), which the main window runs on its own
thread and hands in through reread_done; the window never reads a file or
starts a thread. It holds the states while shown: a 12-player boss
fight's are a median 609 KB and 2.2 MB at most (fight_reread), dropped on
hide (Esc gives a dialog no close event, only a hide) and read again at
the next open, 95 ms at the median.

Which states it takes. It asks for its fight's locator (wanted_locator)
and drops any answer for another: a request the runner superseded still
reports, as 'cancelled', with its old locator. Only a fight the game cut
in two that then went on replaces its entry's locator (every other change
in place leaves the same object: test_fight_locator), and then the window
shows "Reading the fight's lines…" until the new states come. It follows
the new locator when its coalesced redraw runs, the event loop's next
turn, so the main window may compare entry.locator with wanted_locator
before or after it calls entry_updated; and an answer for the entry's new
locator that comes before that turn is taken too. After a Settings
replay rebuilt the entry it keeps the states when the new locator equals
theirs, as a replay of the same log makes it.

The bosses. The game removes some bosses and adds them again, each time
as a new unit with a track of its own: Z'Maja between her phases (three
units in one 5:10 Cloudrest pull), Cloudrest's shades, Halls of
Fabrication's Hunter-Killers at a reset. The canvas draws only the units
present, but the boss bars, the description and the line under the canvas
read every unit, and gave one boss three healths at once ('Z'Maja 56%.
Z'Maja 30%. Z'Maja not in the log yet.', the 56% of a unit that had left a
minute before). They take the bosses from boss_rows: by name, the units
present; else the one that left last, as 'left'; 'not in the log yet'
only while no unit of the name has come. The table keeps every unit, each
with its State.

The table is the reader's surface and the keyboard's. A painted canvas
is a blank to a screen reader (its accessible name, 'Positions', and a
one-line description of the moment in numbers are all it has), while a
QTableView over a model reads as a real table, rows and cells, and a
hidden name cell reads 'hidden name' through Qt.AccessibleTextRole rather
than '@' and shade blocks (measured: build/positions214/paint). Its rows
are the numbered players in number order, then players with no row (no
build in the log, not grouped), then the bosses; a click on a marker
selects its row and a row selects its marker, Enter or a double-click on a
player opens the player window (player_requested). Its rows grow with the
text size: a QTableView keeps 30 px rows at 100%, 150% and 200% text
while the line grows to 16, 24 and 32 px, but sized to their contents
with no word wrap they are 20, 28 and 36 px (probed). They are sized once
for each text size and each new set of rows, not at each step: sized to
contents, the header asked every cell for its size whenever the moment
changed, 936 calls a step and 12 ms of it (profiled over Lord Falgravn's
331 seconds); a step now costs 0.5 to 1.6 ms (positions_canvas has the
measures).

Keys. A window shortcut on a bare key takes it from a focused table (all
21 keys probed), so the window binds modified keys only: Ctrl+Left and
Ctrl+Right step a second, with Shift a tenth; Ctrl+PgUp and Ctrl+PgDn go
to the previous and next death; Ctrl+Up and Ctrl+Down to the previous and
next unit, as they change the player in the player window; Ctrl+C copies
the moment in words, names through the mask. Ctrl+H and the text size
keys are the main window's, application-wide, and never bound here: a
second binding makes both ambiguous and neither fires (probed on Ctrl+0).
The bare keys belong to the focused scrub bar: Left and Right, Shift, Home
and End, PgUp and PgDn. Space alone is not a shortcut, which would take it
from a focused button too: the table and the scrub bar leave a plain Space
to the window (keyPressEvent), which plays or pauses, while a button and
the speed picker keep their own. Ctrl+, and Ctrl+. play slower and faster,
as the < and > of a video player. The buttons are QToolButtons: a
QPushButton in a dialog takes Enter even with the focus elsewhere
(probed); they and the speed picker take the focus by Tab only, so a click
leaves it in the table. Tab goes from the scrub bar to the table to Play,
the speed and the buttons.

Hide names. The main window hands the window the mask of its fight
(NameMask.for_entry, from the entry's player_names). The window extends it
with the players of the locator's unit table, keeping the logging
player's names and hiding every other player's name and character name:
a player who left during the 10 s lead-in is in that table, read before
the roster drops them, but not in player_names. Bosses, adds and pets are
never hidden. On the canvas a hidden name is drawn as '@' and its
pixelated stand-in, as the pages draw it.

Playback (#232). Play runs the moment on from where it is at the speed
picked, 1x to 5x, and only the reader starts it, by Play or Space: no
link, no states read, no speed and no redraw does (the guide's
Accessibility says so, under Motion). The moment is reckoned from the
wall clock, never counted in frames: the moment and the wall time at Play
or at a new speed, plus the wall time since times the speed, so a slow
frame shows a later moment and never slows the fight. Frames come from a
precise QTimer every FRAME_MS, about 30 a second (the measures below),
running only while playing. It pauses by itself at the fight's end
(END_COMBAT, not the tail after it, and never at a death); Play there, or
in the tail, starts again from the fight's start. A step, a scrub or a
death pauses at the moment it goes to, as does a link: the reader asked
for that moment, held still. Selecting a unit, a speed and Show play on,
as they move no moment. A hide stops it, and a minimised window, whose
hide is spontaneous and which keeps its states, pauses: the moment does
not run on unseen. New states, states dropped and a Settings replay pause
too.

Gliding. While playing, a mark moves on a straight line between two
logged samples at most GLIDE_MS (1 s) apart (positions_canvas.glide_state):
from the last line that wrote its place, the reader's seen (a unit
standing still is written again and again, so the state's own time would
start the glide early), to the next state's first, in one map frame and
both on their map. Its facing, health and pools stay the last sample's.
Further apart it waits at its last place, as paused: a line over a longer
gap, which the canvas marks dashed after STALE_MS anyway, would draw a
path the log never gave. Paused, nothing glides: every mark stands where
its last state put it, and Pause redraws the whole moment as a step to it
does, so a paused window is the #214 window to the pixel
(test_positions_playback_gui compares the two).

What a reader reads, while playing. A frame moves the picture, the clock,
the boss bars' paint and the scrub bar's mark. The table, the header, the
line under the canvas, the descriptions (the canvas's, the table's, the
boss bars'), and the scrub bar's value and description follow once a
DESCRIBE_MS (1 s) of wall time, and in full at Pause: a screen reader is
not handed 30 changes a second. Those updates leave the table's scroll and
current row alone; the clock has a fixed size, so its new text asks
nothing of the layout (it asked for one every fifth frame), and the
canvas, which fills itself, is opaque, so the window, the splitter and the
pane under it are not painted again with it.

Measured (build/playback232/measure_paint.py): Lord Falgravn, a 284 s
Kyne's Aegis kill, 12 players with adds, 108 tracks, every frame of the
fight at 1x, offscreen, the machine busy with another job (an earlier,
quieter run of the paused code painted the canvas in 3.3 ms against
5.4). At 200% text and device pixel
ratio 2: the glided scene a median 0.66 ms (p99 1.3; paused, 0.59), the
canvas's paint 5.4 ms (p99 8.7, as paused), a whole frame, tick and
repaint, 7.7 ms (p90 10.4, p99 12.7, at most 16.8), 14 units drawn at the
median and 29 at most. At 100% text and ratio 1: the canvas 3.4 ms, a
frame 4.7 ms (p99 9.2). At 60 frames a second the UI thread would be half
busy at 200% with its p99 frame near the 16.7 ms interval; at 30 it is a
quarter busy with room, and a frame late only skips.

It holds no reference to the main window and stores no lambda on a child;
its timers are its own: the single-shot 0 ms redraw, which draws a burst
of updates to the fight once, and playback's frames.

### src/gui/positions_canvas.py

*[src/gui/positions_canvas.py:1](../src/gui/positions_canvas.py#L1)*

The positions canvas (issue #214): where everyone stood at one moment of a
fight, drawn on a plain 2D canvas, with the boss bars above it and the
scrub bar the moment is chosen on. The positions window (positions_window)
holds the fight and its re-read states (fight_reread) and hands these
widgets a Scene for each moment, held still or, while it plays (#232),
for each frame.

Design: A moment, drawn directly. Nothing moves by itself: the canvas is
repainted on a step, a selection, a resize, a theme or Hide names flip, a
new text size, or a frame of playback, which only the reader's Play
starts, and a full repaint is cheap. Measured offscreen for the study
(build/positions214/paint): 60 markers with rings, noses, bodies and
numbers in 2.2 to 3.4 ms at device pixel ratio 1 and 4.7 to 7.9 ms at
ratio 2; twelve players alone 1.3 to 2.0 ms. Over every second of six real
12-player boss fights (build/positions214/window/probe_piles_out.txt)
this canvas repainted in a median 1.9 to 4.2 ms, a step of the moment cost
0.5 to 1.6 ms and the whole window's repaint 5.7 to 11.3 ms. Played back
at 200% text and ratio 2, a frame of a 284 s Lord Falgravn kill painted
the canvas in a median 5.4 ms on a busy machine, as paused, and built its
glided scene in 0.66 ms (positions_window has the measures and the frame
rate). So there is no sprite or frame cache, no QGraphicsView and no timer
here; the canvas is opaque (it fills itself first), so a frame does not
paint the panes under it again.

Playback glides, a paused moment never does (glide_state, build_scene's
glide): while the window plays, a mark moves on a straight line between
two logged samples at most GLIDE_MS apart, from the last line that wrote
its place to the next state's first, in one map frame, both on their map;
only its place moves. Paused, every mark is where its last state put it.
The window's notes say why.

One box per map frame. The log's coordinates are fractions of the map the
last MAP_CHANGED line named, so places in two frames are never joined: each
frame gets its own box, fitted once to the 2nd to 98th percentile of the
players' and bosses' places in that frame over the whole range, padded by
12% of its longer side, with one scale for x and y and y down. The study
found the min-max box 1.2 to 2.6 times larger, empty for most of a fight.
The moment's frame is the frame of the selected unit's state, else the one
most drawn players are in. A unit whose last state is of another frame, or
far off its map (fight_reread.on_map), is not drawn: the line under the
canvas and the table say "not on this map". A drawn unit outside the
fitted box is pinned to the canvas's edge, with a small arrow towards where
it stands. There is no map art, scale or height (#148 stays parked).

Piles. A group stands close, and a marker's radius grows with the text
size (it must hold '12') while the canvas does not, so numbered players
whose markers overlap by over a quarter (closer than PILE_SHARE radii)
are drawn as one badge that lists them: each member's shape and number
with a short bar of its health, at their mean place, with a dashed line to
it when the badge had to move. The selected player is never piled. Over
six boss fights this gathered 2 to 61% of the players' seconds at 100%
text (Chimera's split the most) and 32 to 90% at 200%, where unpiled
numbers covered each other (the study's critique counted 18 to 82% piled
at 200% with a tighter rule). Badges and labels keep off the players,
bosses, notes and other badges where the canvas has room (_avoid), and
cover least where it has none; a boss's name is never hidden.

Meaning rides on shape, number, arc length and stroke, never on colour
alone, and every mark is in neutral ink. The role hexes are the very
hexes of health 'good', heal, health 'critical', damage and shield
(measured: light T #1565c0 is the recap's shield, D #c62828 its critical
health and damage), so a marker coloured by role would say 'DPS = critical
health'. A player with a row in the fight table is a role shape (circle
for damage, diamond for a healer, square for a tank) filled with the
pane's text ink, holding the row's number in the Base colour (16.1:1
light, 11.4:1 dark). The number font is the application font at 0.78,
bold, in a radius of scaled_px(8): '12' needs 5.9 to 6.5 px at 100% text
and 12.2 to 14.1 px at 200%, and the radius is 8 and 16 px there. Health
is the length of a ring arc clockwise from 12 o'clock, in the death
recap's four health steps, over a decorative 13% track: the steps' closest
pair under deuteranopia is CIEDE2000 2.2 (light), so the length carries the
value and the colour only repeats it. Shield is a thin outer arc in the
recap's shield colour, capped at a full turn of the maximum health. The
nose shows facing in text ink at 75% (7.1:1), the heading taken modulo 2π
with the facing vector (-sin h, -cos h), y down; it is facing, not travel
(the survey: players face their travel in under half their moving steps).

Gaps in the log are marked, never faded. With text ink at 45% a number
on the body reads 3.36:1 (light) and a 30% body 2.12:1, under the app's
4.5:1 and 3:1 floors, so: a unit whose last state is over STALE_MS old is
hollow with a dashed outline; over LOST_MS, hollow and dotted with its
number in muted ink (6.05:1 and 5.22:1); dead, it is hollow in muted ink
with a cross in the recap's damage red under its number, which stays in
full ink. Dead is health 0 (the rule the engine counts deaths by since
#221), and for a player also a death the fight counts, from its moment
until their health next rises (still_dead): the log can write a dead
player's health above 0. A regeneration tick written in the death's own
millisecond after the DIED line kept one player at 631 health for the 17 s
they lay dead, and a mechanic's DIED line carries the health before the
kill; over 1,585 deaths in 9 trial splits, 7 were not at 0 at their own
moment, the moment a death's Positions link opens at. Gaps over
0.5 s are 0.5 to 15.9% of a fight, by log (the study), hence the two
steps. A unit's age counts from the last line that wrote it (the
reader's seen), not from when its state began: the log writes a unit
standing still again and again unchanged (state_age has the measures),
and the table says 'last seen 6 s ago'. Adds keep their own
clock: an add's last line is not its death
(62% of an add's life lies in gaps over 1 s), so a hostile unit is drawn
while its last state is under FORGET_MS old, as a cross for DEAD_ADD_MS
after a state at health 0, then not at all.

The colours. Ink and muted are the fight pane's (fight_render._theme);
health, shield and damage the death recap's (death_render._THEMES), all
pinned by test_palette. New here, keyed {False: light, True: dark} and
measured on the windows11 Base (#ffffff, #2d2d2d): the hostile red of the
adds, 6.65:1 and 4.70:1, and the boss's, 10.30:1 and 6.03:1. The canvas
reads light or dark from its palette's background at paint, as the
timeline strip does, so a theme switch needs only a repaint.

The scrub bar is a QSlider so a screen reader meets a slider with a value
(whole seconds into the fight); Qt gives a QAbstractSlider subclass no
value text at all, and a value text of '1:50.0' would need an accessible
interface made in Python, which crashed at exit in the GUI survey, so the
moment in words is its description. It takes the focus with a mark of its
own: Qt's focus frame (PE_FrameFocusRect) draws a 6,000 px tint over a
100x60 rect in the Fusion style.

### MainWindow.show_moment

*[src/gui/main_window.py:2553](../src/gui/main_window.py#L2553)*

The positions window on the fight *entry* at the moment *t_ms*
(ms since its session's BEGIN_LOG, the locator's own clock), the
unit *unit_key* selected (a player's or companion's row 'unit_id',
which is its FightUnit.key; None for none). The one way in for
every link to it: a row of the Deaths tab, a death's heading in the
player window, the fight header's Positions, and the fight's events
to come. A fight with no locator, or one whose session is not known
(death_render.positions_known), has no such link and opens nothing.

Design: the positions window and the bytes. One window, made at
the first link and kept, like the player window, which draws what
it is given; this window finds where the fight's lines are and has
them read. The places are worked out here, on the UI thread, at a
link whose fight the window holds no states for (_reread_places): a
listing of the split and archive folders, 0.4 to 1.0 ms over a
428-file split folder. The read runs on 'fight-reread' (0.1 s for a
median boss fight, 0.4 s for a long one, 0.6 s from a zip) and its
answer comes back by the bridge (_build_reread). The window shows
words, not a busy bar, while it waits: nothing in the app moves by
itself under Reduce motion. A link to the fight being read asks for
nothing more, and a link to another fight supersedes the read,
whose answer the window then drops.

## Before the first fight: the archive line and recent activity

### src/recent_activity.py

*[src/recent_activity.py:1](../src/recent_activity.py#L1)*

Recent activity: the newest archives of Encounter.log and the newest split
logs, for the window to show while the fight list is empty (issue #191).

Why. At a quiet start the fight list is empty, the pane said only
"Monitoring for encounters…" or "Waiting for Encounter.log…", and the status
bar "No log file" in red; meanwhile the app had just archived the log, and
with *Delete Encounter.log after a verified archive* on, removed it. A
reader could not tell "the app did its job and is waiting" from "something
went wrong and my logs are gone". So the pane names the newest archive and
when it was made, and offers the recent archives and splits, each of which
opens for review.

Which files. The archiver's own, ``Encounter-YYMMDDHHMMSS[-N].zip``
(log_archiver.LogArchiver._archive_target), in the archive folder: the one
set in Settings, else the log's folder, the archiver's rule. The splitter's
own, plain or zipped (split_retention.scan_splits: never a ``-temp.log``
still waiting for its zone, never another tool's files), in the split
folder, the one set in Settings, else the log's folder. Nothing is opened:
a scan is a directory listing, so it can run on the UI thread at every
redraw of the pane.

Which time. An archive shows when it was made, the file's own time, since
"archived at" is what the reader wants to know; the stamp in its name is
the log's newest entry (the archiver names it so), shown beside it as "its
last entry". Archives are ordered by the time they were made. A split shows
its session's start, the stamp in its name, and the splits are ordered by
that stamp, not by file time: the splitter writes some old sessions out
again long after they were played (issue #85; 433 of 899 files in the
maintainer's folder were more than two days off), and by file time an old
evening would head the list.

### src/gui/activity_render.py

*[src/gui/activity_render.py:1](../src/gui/activity_render.py#L1)*

The pane before the first fight (issue #191): what the app is doing, when
Encounter.log was last archived, and Recent activity, the newest archives
and split logs, each a link that reviews it.

The pane is the right place: it is empty exactly then, where the fight
list's rows are a session's fights and a row that opened a file would look
like one, and a dialog would say something was wrong when nothing is. The
first line, in the pane's own text colour, says what is happening; the
archive's detail follows in the muted colour. Archives and splits are
listed apart, five of each: archives are rare (one per gigabyte of log) and
splits frequent, so one list of five would nearly always be five splits
and no archive. The lists start open, since they are the proof the reader
came for (a UX review of 2026-11-03: a page that is three lines and white
space, with the proof behind a link, reassures nobody); the Recent
activity link closes them, and the choice is kept for the session.

Each group's heading counts the files and their bytes on disk rather than
naming the folder: "how much" is what a worried reader wants, and the full
path is on each file's hover. A link to a file carries its place in
activity_paths, never the path: a path put in an href comes back through
QUrl with its percent-encoding undone here and there, and the window holds
the list the page was drawn from anyway. Clicking one runs Open log for
review on it, the toolbar action's own path, so a zipped split or an
archive streams from its zip and a large log is outlined and the reader
asked first.

With no log and the app's own archive to explain it, the first line says
so in the words of the setting that did it (*Delete Encounter.log after a
verified archive*), and the advice on turning logging on goes last, under
the lists, since it is then a reminder and not a fix; with nothing to
explain the absence, the advice follows the first line as it always did.
The explanation comes from this session's archive event (the archive
whose completion deleted the log, ArchiveEvent.original_deleted), never
from the setting and an archive's mere presence: an old archive beside a
log missing for another reason (Settings pointing at a mistyped path, the
game writing elsewhere) must not turn that problem into a reassurance.

## Updates: the schedule, the conditional request and the button

### src/update_check.py

*[src/update_check.py:1](../src/update_check.py#L1)*

Update check against GitHub releases (stdlib only, no extra dependencies).

Queries the repository's latest release and compares its tag against the
running version. Network problems are never fatal: every failure is a
result the caller can read, and the app carries on.

Design: the check repeats every 15 minutes while the app runs (issue #56,
2026-10-26; gui/update_poller.py has the schedule), so it is conditional.
GitHub returns an ``ETag`` with every reply; sent back as
``If-None-Match``, an unchanged release is answered ``304 Not Modified``
with no body. GitHub limits unsigned requests to 60 an hour per address
and does not count a 304 against that limit, so four checks an hour cost
nothing while nothing changes, and a household of several copies behind
one address stays far under the limit; a plain GET each time would spend
four of the 60 per copy for a few KB of unchanged JSON. A limit reply
(403 or 429) names a reset time in ``X-RateLimit-Reset`` (epoch seconds)
or ``Retry-After`` (seconds); the result carries it, capped at an hour
from now, and the poller makes no request before then. The ETag is kept
for the run only, so each start sends one full request.

The release body is GitHub's generated notes (one line per pull request
and a compare link), shown in the ⓘ popup beside the Update button; the
release date comes from ``published_at``.

Two channels (issue #134, 2026-10-29). Stable reads ``/releases/latest``,
which GitHub never points at a prerelease or a draft, so it follows a
release made Stable, or taken back, exactly. Beta reads the newest ten
releases (``/releases?per_page=10``, about 80 KB for a full reply, then
304s like the latest endpoint) and offers the highest version among them,
prerelease or not. Every release is published as a prerelease, a beta, and
a promotion makes one a full release (scripts/promote_release.py), so Beta
gets each release at once and Stable the ones made Stable; until the first
beta (0.26.0 and before) every release was a full one. A demoted release
is a draft again, which neither endpoint shows without a login. A release
counts only when its tag is exactly
``vX.Y.Z``: the list also carries data releases (``esobuild-assets-<update>-
<date>``), and a search for three dotted numbers anywhere in a tag would
read any such tag as a version. Neither channel offers a version lower
than the one running, so someone who leaves Beta keeps the version they
have until a Stable release passes it.

### src/gui/update_poller.py

*[src/gui/update_poller.py:1](../src/gui/update_poller.py#L1)*

The update poller: when the app asks GitHub for a newer release, and on
which thread.

Design: the check runs 3 s after the window is built and then every
``update.check_interval_min`` minutes (default 15), for as long as the
Settings box is ticked, so an app that runs through a raid night learns of
a release published after it started. Issue #56 (2026-10-26) asked for
this in place of the one check at startup and the pop-up it opened.

Each check is a conditional request: the ETag GitHub returned with the last
full reply goes back as If-None-Match, and an unchanged release is answered
304 with no body, which GitHub does not count against its limit of 60
unsigned requests an hour per address (update_check has the figures). A
rate-limit reply names a reset time, and no check runs until then.

The network call and the installer download run on a daemon Python thread,
not on the engine thread as they did until 0.14.2: there a wedged network
stalled fight updates for the 10-second timeout, and a download for its
whole length; once per run that was bearable, every 15 minutes it is not.
The thread calls update_check functions only, creates no Qt object and
holds no widget, and hands its result back through a signal carrying plain
data, which Qt queues to this object's thread, the UI thread (see
engine_worker.py and the 0.6.x settings crash for why a Qt object must
never be freed off the UI thread). One check or download runs at a time; a
tick during one is skipped. A result that arrives after stop() is dropped
(the generation counter), so a closing window never hears from a late
thread.

start() clears the ETag so its first request is a full one: Settings saved
with the check on also clears a skipped version, and a 304 would otherwise
hide the release that was skipped and is wanted again.

Each check reads the channel from the config (``update.channel``, issue
#134). The two channels ask different endpoints, and the channel changes
only through a Settings save, which calls start(): that clears the ETag, so
no validator is ever sent to the other endpoint. start() also withdraws an
offer the previous channel made at once, rather than when (or if) the
first check on the new channel succeeds: someone who leaves Beta while
offline or rate limited must not be left one click from the beta they
opted out of.

### src/gui/update_popup.py

*[src/gui/update_popup.py:1](../src/gui/update_popup.py#L1)*

The ⓘ popup beside the Update button: the release on offer, its date, its
notes as GitHub publishes them, links to the release page and the
changelog, and the way to skip the version. A Qt.Popup frame like
BuildIssuesPopup: it closes on a click elsewhere or Esc and deletes itself,
and nothing keeps a reference to it.

The notes are GitHub's generated release notes (one line per pull request
with its link, and a compare link), rendered from markdown; the
maintainer chose them on 2026-10-26 over the CHANGELOG entries, which run
to a dozen lines each and are one click away through the Changelog link.
The notes are the offered release's own, so someone several releases
behind (a Stable user, issue #134, skips every beta in between) would see
only the last step; the "Changes since" link compares the running version
with the offered one on GitHub, however many releases lie between.

## Releases: every tag a beta, and a beta made Stable

### scripts/release.py

*[scripts/release.py:1](../scripts/release.py#L1)*

Make a release's commit, or tag a release once its pull request is merged.

Design (issue #134, task 2.5; the maintainer's decisions 11 and 12 of
2026-10-29): every session cut releases its own way, and almost every pull
request edited the same lines of two shared files, the top of
CHANGELOG.md and docs/design.md, so each merge put every other open pull
request in conflict (24 merges of main into PR branches in five days).
Three changes together end that:

- A change adds its notes as a fragment, ``changelog.d/<issue>-<slug>.md``,
  written under the same ``### Added`` / ``### Changed`` / ``### Fixed``
  headings CHANGELOG.md uses. Two pull requests never edit the same file,
  and the CI check (scripts/changelog_check.py) asks every pull request for
  one.
- ``docs/design.md`` is rebuilt in the release commit only. Between
  releases the docstrings it is built from are the source; a tag whose
  design notes lag the code is refused, here before the tag is made and in
  the tag's workflow run before either build (build_design_doc --check).
- This script makes the release commit's edits the same way every time:
  the version in src/version.py, the fragments gathered under
  ``## [X.Y.Z] - YYYY-MM-DD`` at the top of CHANGELOG.md (an
  ``[Unreleased]`` section a branch from before fragments still carries at
  the top is folded in, not lost), the fragments removed, the design notes
  rebuilt, and one commit, ``chore: release X.Y.Z``. Sections come out in
  Keep a Changelog's order and, within a section, in fragment file name
  order, so the same fragments always give the same text. Everything that
  can refuse (an unreadable fragment, one git does not track yet, a design
  note that cannot be built) is checked before the first file is written,
  so a refusal never leaves a release half made.

The release commit goes inside the last pull request of the release, or one
of its own, since main takes pull requests only. The script refuses to
commit on main or over uncommitted changes, and the version must be higher
than the current one. ``minor`` or ``patch`` picks the next number; the
choice stays the releasing session's (a release with only Fixed entries is
a patch).

A fragment can reach the release branch after the release commit: the
branch must be up to date with main to merge, and a merge of main brings in
whatever merged meanwhile. Its change would ship in the build while its
note waited for the next release. The Changelog check refuses a release
pull request that still holds fragments, and ``--tag`` refuses such a merge
commit; the remedy is to drop the release commit (``git revert``) and run
the script again.

Once the pull request is merged, ``--tag X.Y.Z`` finds the commit on
origin/main that first carries the version (the merge commit, on main's
first-parent line), runs the release job's tag checks on it
(scripts/release_guard.py), checks its design notes and its changelog.d/,
and makes the annotated tag. Pushing the tag publishes a beta to every
install on the Beta channel, so it happens only with ``--push``, and
``--dry-run`` runs every check and makes nothing. ``--watch`` then follows
the tag's workflow run and checks what it published: a pre-release with
all three files, and ``/releases/latest`` (Stable) not moved. Making a beta
Stable stays scripts/promote_release.py's, on the maintainer's word.

Needs git; ``--watch`` needs the GitHub CLI, logged in.

```
    python scripts/release.py minor|patch|X.Y.Z [--date YYYY-MM-DD] [--trailer TEXT] [--dry-run]
    python scripts/release.py --tag X.Y.Z [--dry-run | --push [--watch]]
```

### scripts/changelog_check.py

*[scripts/changelog_check.py:1](../scripts/changelog_check.py#L1)*

Check a pull request's changelog fragment and its hands-off files.

Design (issue #134, task 2.5): changes write their notes as fragments in
changelog.d/ and the release commit (scripts/release.py) gathers them into
CHANGELOG.md and rebuilds docs/design.md. A pull request that is not a
release is refused when it:

- adds no fragment of its own (a new ``changelog.d/<name>.md``, directly in
  the folder, not the README), unless it carries the ``no-changelog``
  label: its change would reach the release notes only if someone
  remembered. Editing a fragment already there is not a note of its own,
  and a file in a subfolder is one the release script never reads;
- edits CHANGELOG.md: that edit is what put every open pull request in
  conflict with the others;
- edits docs/design.md: the same, for the design notes, which the release
  commit rebuilds from the docstrings.

The label waives the first rule only: the other two are the conflicts the
whole change exists to end.

A release is a pull request that changes ``__version__`` (read from the
merge base and the head, so an unrelated edit of src/version.py is not
one). It does all three by design and passes, unless changelog.d/ still
holds fragments at its head: they came in with a merge of main after the
release commit, their changes would ship in the release and their notes
in the next one. Reverting the release commit and running the release
script again gathers them.

The fragment's text is not checked here: scripts/release.py refuses one it
cannot read when the release is cut, and the unit tests run the same parser
over every fragment on the branch.

```
    python3 scripts/changelog_check.py <base sha> <head sha> [--labels a,b]
```

### scripts/release_guard.py

*[scripts/release_guard.py:1](../scripts/release_guard.py#L1)*

Check a version tag before the release job publishes it, and name the
tag its notes start from.

Design (issue #134, 2026-10-29): the release job publishes whatever tag
reaches it, and nothing checked the tag until now. Three refusals, each
before anything is published:

- the tag must be exactly ``vX.Y.Z``: the app's update check counts only
  such tags, and data releases (``esobuild-assets-<update>-<date>``) are
  created by hand, never by this job;
- it must equal ``v`` + ``__version__`` in the tagged commit's
  ``src/version.py`` (read from the commit, not the checkout): the assets
  are named from that file, and the app compares its own version with the
  tag, so a mismatch would offer an installer that reports the wrong
  version (a tag pushed on the wrong commit, or a release commit missing);
- its commit must be on ``main`` (``git merge-base --is-ancestor``): tags
  are outside the branch ruleset, so a tag on an unmerged branch would
  publish code no pull request merged.

The previous ``v*`` tag (``git describe`` from the tagged commit's first
parent, which for a merge commit is main as it was) goes to the job's
output as ``previous``: GitHub's generated notes then cover the changes
since the release before this one, whichever release GitHub would
otherwise have picked as the base. Every release is now born a beta, and
with a Stable release as the latest GitHub may compare against that.

Standard library and git only; the job runs it on the runner's own Python.

```
    python3 scripts/release_guard.py <tag> <commit> [--main-ref origin/main]
```

### scripts/promote_release.py

*[scripts/promote_release.py:1](../scripts/promote_release.py#L1)*

Make a beta the Stable release, take a Stable release back, list the
betas that could be promoted, or open a reminder when Stable falls behind.

Design (issue #134, the maintainer's decisions of 2026-10-29): every tag is
published as a GitHub pre-release, a beta. Promoting turns that same
release into a full one and marks it latest, so Stable users run exactly
the build beta users ran, and ``/releases/latest``, which the app's Stable
channel and the home page read, moves to it. Nothing is rebuilt or
retagged.

A beta may be promoted when:

- it is newer than the Stable release and carries all three files;
- it was published at least 48 hours ago;
- the maintainer used it live, in at least one session with fights; the
  script cannot see that, so ``--used-live`` says so;
- no issue labelled ``regression`` affects it. A regression issue names the
  version that brought the fault in as the first ``X.Y.Z`` in its title
  (never its body, where a pasted "Python 3.14.10" would read as a
  version). While open it affects that version and every later one; once
  closed, those published before it was closed, since the fix can only be
  in a later release. So a fixed regression still marks the versions that
  carried it, which is the rule "no later beta fixes a fault in it". A
  regression whose title names no version affects every release until its
  title does: a rule that cannot be read must stop a promotion, not let it
  through. An issue that turns out not to be a regression loses the label.

``--force "<reason>"`` overrides the last three rules and writes the reason
into the release notes (a crash fix that cannot wait two days); the first
is never overridden.

The release notes are rewritten as the changes since the previous Stable
release: every pull request line of the releases in between, oldest first,
without repeats, and the compare link. The app's update popup shows a
Stable user these notes, and a Stable user skips every beta in between.

``/releases/latest`` can lag a minute behind a change (seen on
2026-10-28), so the check of it retries once. The script then starts the
Pages workflow, which rebuilds the home page's buttons on main: a
``release`` event would run on the tag, and the github-pages environment
deploys from main only.

``--demote`` pulls a bad Stable release: it becomes a draft again and the
previous Stable release is marked latest. A draft is invisible to the app
(both channels read without a login, which never sees drafts), to the home
page and to ``--candidates``; left a pre-release it would still be the
newest beta, offered on Beta and on the home page. Installs that already
updated keep it. ``gh release edit <tag> --draft=false --prerelease``
publishes it again as a beta.

``--candidates`` lists the betas newer than Stable and what each still
lacks: a session uses it to propose a promotion, never to make one.
``--remind`` (the weekly workflow) opens an issue when the oldest beta that
meets the time and regression rules was published more than 14 days ago,
which is a beta that has waited two weeks for a decision, unless one is
open already.

Needs the GitHub CLI, logged in (``GH_TOKEN`` in a workflow).

```
    python scripts/promote_release.py vX.Y.Z --used-live [--dry-run]
    python scripts/promote_release.py vX.Y.Z --force "crash fix" [--dry-run]
    python scripts/promote_release.py --demote vX.Y.Z [--dry-run]
    python scripts/promote_release.py --candidates
    python scripts/promote_release.py --remind [--dry-run]
```

### scripts/build_site.py

*[scripts/build_site.py:1](../scripts/build_site.py#L1)*

Build the home page (site/) into _site/ for GitHub Pages.

The page is a hand-written index.html whose download buttons need the
current release: the release assets carry the version in their names
(esolog-tail-windows-setup-0.13.3.exe), so no fixed link can point at the
latest installer. This script reads the latest release from the GitHub API,
fills the page's placeholders, and copies the page, its favicon and social
card, and the screenshots it uses from docs/screencaps/ into _site/.
.github/workflows/pages.yml runs it and publishes _site/.

Placeholders in index.html are {{name}} for the names in release_values()
plus {{site_url}} and {{beta_line}}. A placeholder left unfilled, a missing
asset or an unreadable release fails the build: a page with holes must not
be published.

The buttons name the latest release, which is the Stable one: every release
is published as a pre-release, a beta, and only a promotion makes one the
latest (issue #134). {{beta_line}} is a smaller line under them naming the
newest beta when one is newer than Stable (the maintainer's choice of
2026-10-29), and nothing otherwise. It is a nicety: if the release list
cannot be read, the page is built without it rather than not at all. It
says to choose Beta in Settings, since the app starts on Stable whichever
installer it came from. The beta is picked by the app's own
``update_check.newest_release`` (src/, standard library only), so the page
and the app's Beta channel cannot disagree on which release is the beta.

Standard library only, so the Pages job installs nothing.

## Taunt marks that pulse in a text page

### ringed

*[src/gui/icon_cache.py:26](../src/gui/icon_cache.py#L26)*

A copy of *image* with a ring of *color* just inside its edge: about
an eighth of the icon wide (8 px on the bundled 64 px icons), a dark
hairline outside it so it reads on any icon art, and a light hairline
inside. *phase*, 0 to 1 around one glow cycle, brightens the ring from
the colour itself (0) to a paler, lighter tone (0.5) and back, which the
fight view steps through to make a taunt mark pulse (issue #12).

### FightView._pulse_step

*[src/gui/fight_view.py:784](../src/gui/fight_view.py#L784)*

Design: Taunt marks pulse. A QTextBrowser page cannot animate, but
the document asks for an image's resource each time it paints, and
one set with addResource is taken before loadResource is asked. So
every ringed icon the page has loaded is redrawn at the next phase
of the glow (IconCache keeps PULSE_STEPS images per ring colour) and
the viewport repainted: a few small images and a repaint every
PULSE_INTERVAL_MS, no layout, so the page never moves. The timer
runs only while the page holds a ringed icon and the view is shown.

## Hidden names: the stand-in behind the blur

### src/gui/name_mask.py

*[src/gui/name_mask.py:1](../src/gui/name_mask.py#L1)*

Design: Hidden names. A screenshot of a fight, or a fight pasted into a
chat, shows the handles and character names of everyone in the group. The
Hide names switch (issue #72) keeps the name of the player whose client
writes the log and hides everyone else's, in every place the app shows a
name: the fight pane's rows and hover texts, the build, damage and
death-recap windows, the dps graph's legend, the timeline strip's hover
and pop-ups, and the Copy fight text. Enemy, pet, set and ability names
are never hidden.

Who is kept is read from the log, not configured: the game writes
``isLocalPlayer`` on every player's UNIT_ADDED line, ``T`` for the one
client writing the log (checked over 899 split logs: exactly one per log,
the same handle on 14 characters, the flag in the same place since the
oldest log of 2025). The engine puts it on each fight entry's player as
``is_local``. A reviewed log written by a friend therefore keeps the
friend, which is what "the handle of the person logging" means.

Which names are player names: a name is hidden when it is not the local
player's handle or character name and either starts with ``@`` or is the
character name of another player of the fight. The ``@`` rule reaches
every nested place a handle appears (the source of a heal in a death recap,
a caster in the penetration section, a timeline interval's source and
target) without threading the player list into each; the character-name
set reaches a player the log gave no handle. That set is read from the
entry's ``player_names``, every player unit the engine saw, rows or not:
a player whose PLAYER_INFO never reached the log has no row in the table
but still casts, heals and dies in the fight's other data (the review of
2026-10-27 found the gap when the set was read from the rows alone).
``anon`` (the engine's word for a player with neither handle nor name)
and enemy names fall through, as no enemy, pet, set or ability name
starts with ``@``. An entry with no local player at all hides every name,
the safe direction.

A companion is named after its owner, "<owner>'s Companion" (companions.py).
The owner part is hidden or kept as the owner's own name would be, and the
"'s Companion" after it always shows, so the logging player's companion
stays readable and another player's reads "@▒▒▒▒'s Companion".

How a hidden name looks: the maintainer asked for a blurred or pixelated
name, the look of a screenshot with the names smudged out. The pages
drawn as rich text (the fight pane and the three windows) get a pixelated
word of the hidden name's length, its ``@`` left readable as text so the
row still reads as a handle. That word is **not** the real name pixelated.
Pixelated or blurred text can be read back when the font, the size and
the rendering are known (they are all public here) and the words are
short, so a picture meant to hide a handle would carry it. Instead the
mask makes a stand-in word from a keyed hash of the name (``stand_in``:
the key is random per run, so the same name gives the same word in every
row, window and pop-up of a run, and nothing persists), draws it in the
page's font at the requested size and weight, downscales it smoothly by
the block size and scales it back with nearest-neighbour. The result has
the blocky texture of a pixelated word, the ascender and descender
pattern of a word nobody has ever seen. The length is kept so the row's
columns stay where they were; a handle's length identifies nobody.

Where text is all there is (a tooltip, the strip's pop-up, the graph's
legend, a window title, the clipboard) a hidden name is ``@`` followed by
one shade block per hidden character: a QLabel cannot ask a view for an
image.

The page asks for the image by URL, ``mask:<word>?color=rrggbb&pt=<n>&b=<0|1>``
(``image_html``), answered by ``FightView.loadResource`` from
``mask_image`` with the view's font family and device pixel ratio, cached
for the run by its parameters, as the link glyphs are (see gui.glyphs).
The word is lower-case letters and underscores for spaces, so the URL
needs no escaping and a malformed one is refused.

## Links in the fight pane: the hover cue and the dps glyphs

### FightView._show_hover_cue

*[src/gui/fight_view.py:647](../src/gui/fight_view.py#L647)*

Design: the hover cue. Underline the hovered player name or dps
figure in the link color; any other target, or none, clears the cue.

A name or dps figure keeps the look of plain text in the page (the
figures carry a glyph beside them, see gui.glyphs; the names do not,
since twelve underlined or blue names would be clutter). Qt rich text
has no hover styling, and changing the document's own character
format on hover would enter the undo stack, relayout the page and
invalidate the cursors the in-fight search holds. So the cue is an
extra selection: a format painted over a text range without touching
the document. The search's highlights are extra selections too, and
setting one list replaces the other, so the view owns both lists and
applies their union. The selection covers the anchor's text and stops
at its glyph, which is an image fragment of the same anchor; the
glyph still triggers the cue and the tooltip, since the pointer on it
is the pointer on the anchor.

### src/gui/glyphs.py

*[src/gui/glyphs.py:1](../src/gui/glyphs.py#L1)*

Design: Link glyphs. The fight pane has three kinds of link that are not
ESO-Hub pages: a player's name opens their build window, their dps figure
their damage window, and the header's group dps figure the dps over time
graph. All three are drawn as plain text in the pane's own colours, by
choice: twelve underlined or blue names in a trial fight would be clutter,
and the name is the row's identity. The cost is that nothing says they can
be clicked until the pointer is on them (the hover cue, see
FightView._show_hover_cue), and the two dps figures suffered most: the
group figure sits in the muted stats line where nothing else is clickable,
and the damage window has no other way in at all (issue #34).

So the two figures carry a small glyph inside their anchor, drawn here with
QPainter rather than shipped as a file: after the group figure, a short
polyline in the graph's own line style (about 2 px, round joins) in the
theme's link colour, the one coloured mark in that grey line; after each
player's figure, three bars, longest on top, in the muted colour, since
there are up to twelve of them. Being inside the anchor, a glyph is part
of the click target and of the hover: the view underlines the text beside
it and shows the same tooltip. The glyph follows the pane's font size and
is drawn at the view's device pixel ratio, so it stays crisp on a scaled
display (Qt lays out an image that carries a device pixel ratio at its
logical size). Names stay plain, with their hover cue.

The (i) of possible build issues is drawn here too (issue #140). It was the
font's ⓘ in the link colour after the class text, where it drifted right
with the text's length, thin and among muted words, and was easy to miss;
the first-damage * after the name was the mark people saw. It now sits on
the name, right after it (where the * was until issue #159 moved who
opened the fight to a line under the table), bold with a faint halo of its
own colour. Qt rich
text has no text-shadow, filter or opacity, so the glow cannot come from
the page: the glyph is a ring about the size of the font's ⓘ (11.5 px of
11 at 9 pt), half again as heavy, over a radial gradient that is clear
inside the ring, about two fifths opaque at its outer edge and nothing at
the image's edge; the clear inside keeps the i at the link colour's full
contrast (issue #77). The image is as tall as the text line, so the halo
has 2 to 3 px around the ring, and aligned to the line's top: Qt centres
a middle-aligned image on half the x-height above the baseline, which
pushed a line-tall image 2 px under the line and made each marked row
taller. The main window passes the fight view's line height into the page
(render_html's line_px), so the image fits whatever font the system gives;
without it the page estimates the line as 1.3 em, Segoe UI's. A death
chip or a hidden name's stand-in on the same line adds only descent, so
the line's top, and the ring with it, stays level with the name. At 100%
scaling the ring's inside is 8 px tall, and a dot and stem placed freely
ran together into a bar touching the ring, so the i is laid out in whole
device pixels from the image's own width (issues_i_layout): a 2 px dot, a
clear pixel, a 3 px stem, and a clear pixel above and below. No
pulse: a still mark, so Reduce motion has nothing to stop. The fight
list's ⓘ is list text, which cannot be bold or glow without a delegate,
and the popup is a label that cannot serve these images; the build window
shows the popup's list, so all three keep the font's ⓘ.

The page asks for a glyph by URL, ``glyph:<kind>?color=rrggbb&px=<n>``
(fight_render.glyph_html), which FightView.loadResource answers from here:
one image per kind, colour, size and ratio, kept for the session.

## The text size

### src/gui/text_size.py

*[src/gui/text_size.py:1](../src/gui/text_size.py#L1)*

The app-wide text size (issue #77): one percentage of the system font,
saved as display.text_scale, set from Settings or with Ctrl+=, Ctrl+- and
Ctrl+0.

Design: the size is applied with QApplication.setFont, so every widget
that has not set a font of its own follows it, and every rendered page,
which sizes its text from its view's font (base_pt), follows it on the
next render. What is drawn in pixels rather than points (the timeline
strip's rows and label column, the dps graph's margins and legend, the
icons in rendered pages) asks scale() and grows with it, but never
shrinks below its size at 100%: icons and rows that small stay legible,
and at 100% everything is drawn exactly as before the setting existed.

The system font is read once, before the first change, and every
percentage is of that font, so stepping up and back down returns to the
same size rather than drifting with rounding. Qt is imported only where a
font is set, so the page renderers can ask scale() without it.

QApplication.setFont posts the change to each widget rather than sending
it, so straight after it every view still reports the old font, and a page
rendered then from its view's font comes out at the old size (the
Settings path did just that: Save, redraw, old size). apply() delivers the
posted font changes before it returns.

## The trial score banner

### src/banner_capture.py

*[src/banner_capture.py:1](../src/banner_capture.py#L1)*

The trial completion banner, captured from the screen after END_TRIAL (issue #167).

Design: The score banner. When a trial or a veteran arena completes, the game
shows "COMPLETED: SUNSPIRE (VETERAN)" with the final score, the time, the
vitality bonus and the revives used, for ten seconds (TRIAL_COMPLETE_LIFESPAN_MS
in the game's centerscreenannouncehandlers.lua; one handler,
EVENT_RAID_TRIAL_COMPLETE, serves trials and arenas alike). Keeping a picture
of it is the traditional record of a run. The log writes END_TRIAL at the same
moment (the engine's _handle_end_trial), so the app can take the picture
itself, on Windows: it grabs the screen once a second, reads each grab with
Windows' own text recognition, and keeps a grab in which the run's score
appears, cropped to the banner, as a PNG. The score makes the capture
*verified*: the digits of the log's finalScore must be read off the picture,
so the file can only be this run's banner, whatever the client language. The
game's own timer text (trial_result.duration_text) is the fallback for a score
the recognition split badly. Nothing is kept when no grab verifies (the game
in exclusive fullscreen, alt-tabbed away, no recognition language installed,
the banner never shown); the app's diagnostic line says so.

When the banner comes (issue #183): it waits in the game's announcement queue
behind higher priorities (champion points, experience, objectives, quest
updates; 3.5 s each), so a trial's showed 0.5 to 4 s after END_TRIAL and
Maelstrom Arena's about 25 s after it, at the end of an arena that queues
several. The burst therefore runs until END_TRIAL's own time plus
BURST_UNTIL_S, and for at least BURST_MIN_SECONDS when the line is read late
(burst_seconds): Vateshran Hollows' line, read 1 s late, was given only 15 s
and its banner came after; Maelstrom's, read 21.5 s late, was caught as it
appeared.

Keeping a whole banner: the banner is drawn in left to right over 1,700 ms
(CenterScreenLargeTextWipe in centerscreenannounce.xml) and drawn out over
2,000 ms at the end, so the first grab that verifies can hold part of it (the
Maelstrom file of 2026-11-01 stops at "Vita"). After it, FOLLOW_UP_GRABS more
are taken of the same monitor, a second apart, and the most complete one is
kept (more_complete): the one that reads the vitality bonus's digits, then the
one whose stats row reaches furthest right, a later one on a tie.

Why text recognition rather than a fixed rectangle: the banner's position is
in the game's UI units (230 from the top, centred, in centerscreenannounce.xml),
which scale with the resolution and the UI scale setting, so the crop comes
from the boxes the recognition returns for the title and the stats row. The
banner is centred on the screen, so the crop is made symmetric about the
screen's centre line: the left edge the words give fixes the right edge too,
which keeps the vitality icon and the revives count the recognition never
reads, and the undrawn part of a banner caught mid-wipe. (A game in a window
off the screen's centre is the case this misjudges.) Only the top-centre of
the screen (REGION_WIDTH_FRACTION by REGION_HEIGHT_FRACTION, centred, so its
centre is the screen's) is read and only the banner band is kept, so the
group frames and the chat stay out of the picture and the Hide names switch
needs no change.

What each burst saw goes into banner.log beside crash.log (burst_log_text,
append_burst_log): the run, when END_TRIAL was written and read, the outcome
line, and one line per grab with the monitor, frame, how many lines were read
and whether the score or the time matched. Of the recognised text only the
lines holding a digit are kept in full (the stats line, the timer); other
announcements pass through the region, so the rest is only counted (Chris,
2026-11-01). No pictures: an unverified grab is never kept. The newest
BANNER_LOG_BURSTS bursts are kept.

Why Windows PowerShell: Windows.Media.Ocr is a WinRT API that Windows
PowerShell 5.1 (on every Windows 10 and 11) can call, so no package is needed;
pwsh 7 cannot, lacking the WinRT projection. One process serves a whole
burst, fed file paths on its standard input, which saves the 1.3 s start per
grab. The paths must be long paths: the WinRT StorageFile refuses 8.3 short
names. The engine is the user's profile language, or the first installed
recognition language; none at all is the unverified case.

Why Desktop Duplication (desktop_duplication) rather than Qt's screen grab:
on an HDR desktop every 8-bit grab comes out washed-out, the desktop being
composed in linear scRGB. Duplication hands the FP16 desktop over as it is,
and gui.banner_burst.frame_to_image turns it into sRGB: divide by the display's SDR white level
(DisplayConfig's DISPLAYCONFIG_SDR_WHITE_LEVEL, in units of 80 nits), so the
brightness Windows shows SDR white at lands on white, then Qt's colour-space
conversion from linear to sRGB. Qt's grab (QScreen.grabWindow) is the fallback
when duplication is refused, as it is in a remote session.

### src/desktop_duplication.py

*[src/desktop_duplication.py:1](../src/desktop_duplication.py#L1)*

One frame of a monitor through DXGI Desktop Duplication, in the desktop's own pixel
format: BGRA8 on an SDR desktop, RGBA16F (linear scRGB) when Windows HDR is on.

Design: Desktop Duplication through ctypes. The trial completion banner (issue #167)
must be captured on an HDR desktop, where every 8-bit grab (GDI, Qt's
QScreen.grabWindow, Windows Graphics Capture with an 8-bit format) comes out
washed-out: Windows composes an HDR desktop in linear scRGB floating point and the
8-bit paths clip it without the transfer curve. Desktop Duplication hands the
composed desktop over as it is, R16G16B16A16_FLOAT when HDR is on, so the
conversion to sRGB can be done properly (gui.banner_burst.frame_to_image). The
packages that wrap the API either need numpy and OpenCV (windows-capture, about
150 MB in the frozen app) or still need a Direct3D device made by hand (pywinrt), so
the API is driven directly through ctypes: a Direct3D 11 device per adapter, its
outputs enumerated through DXGI, IDXGIOutput5::DuplicateOutput1 asked for FP16 or
BGRA8 frames, each frame copied to a staging texture and mapped for reading. The
vtable positions below are the declaration order of d3d11.h and dxgi1_5.h; a wrong
one crashes the process, so run_self_test() exercises every call on a real desktop.

The first AcquireNextFrame after DuplicateOutput often returns an empty texture
(LastPresentTime 0: no desktop image presented since the duplication began), so
grab() keeps acquiring until a presented frame comes or the deadline passes.
Desktop Duplication is refused inside some remote sessions and on an output that
belongs to another adapter than the device, which is why every adapter gets its
own device.

### src/gui/banner_burst.py

*[src/gui/banner_burst.py:1](../src/gui/banner_burst.py#L1)*

The burst that captures the trial completion banner (issue #167): the GUI
side of banner_capture.

Design: The capture burst. A BannerBurst lives on the UI thread, owned by the
main window, one at a time, started the moment the engine reports END_TRIAL
(on_trial_result), before the fight that carries the result is finalized:
END_COMBAT trails a successful END_TRIAL by up to six seconds on the real logs,
and the banner is on screen for ten. All the work runs on the burst's thread:
it opens a Desktop Duplication reader per monitor (desktop_duplication; a lost
desktop, a mode or HDR switch, is reopened once), and once a second until
END_TRIAL's own time plus 45 s (banner_capture.burst_seconds) grabs every
monitor, converts the frame (frame_to_image), cuts the top-centre region
(banner_capture.region_rect), writes it as a PNG in a temporary folder, reads
it with the Windows recognition (one PowerShell process for the whole burst)
and verifies it against the run's score. The UI thread only takes part when no
monitor can be duplicated (a remote session), grabbing through Qt's QScreen,
which must be used from the UI thread, and handing the images to the thread.
The first verified grab is followed by banner_capture.FOLLOW_UP_GRABS more of
the same monitor, a second apart, for a banner still drawing in; the most
complete verified one (banner_capture.more_complete) is then cut out of its
PNG, symmetric about the screen's centre line, and saved under the run's name
in the banner folder. A burst that runs out with nothing verified ends with
nothing kept, and the reasons the thread noted (no duplication, a lost
monitor) go into the status-bar line. Every outcome, a cancelled burst's too,
is written to banner.log with a line per grab (banner_capture.burst_log_text).
The thread holds frames, images, paths and text, never a widget, so nothing of
Qt's widgets is touched off the UI thread (the rule of issue #18); the burst
deletes itself after it reports.
