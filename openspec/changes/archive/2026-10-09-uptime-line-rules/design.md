# Design: The uptime line as rules, and boss debuffs in trash packs

## Context

0.8.0 shipped tracked effects (`effect_rules`): rules measured by uptime or stacks on a scope, beside the six group buffs and the taunt the engine still tracked in code. Twelve split logs of 2026 (376 fights, Maw of Lorkhaj, Rockgrove, Dreadsail Reef and nine dungeon or Infinite Archive runs) were replayed before deciding anything:

- 281 of the 376 fights had no boss; the group hit up to 71 mobs in one. Boss debuffs reach many of them at once: Off-Balance 27 of 32 mobs (7 at once), Major Vulnerability 7 of 18, Minor Brittle 18 of 32, the taunt 20 of 32. In boss fights the same effects were on the adds too in about half the fights, never on the adds alone.
- 124 of the 376 fights ended with a tracked span still open on a unit that had died or been removed: the game writes no FADED for many of a corpse's effects, and such a span ran into every later fight of the zone.
- The taunt's measure from issue #9 (each boss to its death, the mean over the bosses) and a plain union over the bosses to the fight's end differ in 39 of 95 boss fights, by up to 83 points where a boss died early and the fight ran on against its adds.
- The six group buffs as `on group` rules read the same as the engine's code in 690 of 745 readings; in the other 55 (46 of them Major Courage) the rule read higher, never lower, because the code ignored an UPDATED refresh when it had missed the GAINED before it.
- Replaying the sample through the committed and the changed engine (525 fight events, thirteen logs): every field but the uptime line identical; the group buffs identical but for 18 refresh cases; the taunt identical in 52 of 79 boss fights and higher in 27 (lower in one by 5 points), because the old encounter-scoped taunt spans were lost at each BEGIN_COMBAT (a pre-pull taunt counted only from its next refresh) and because a boss that arrived after the pull was measured from the fight's start; one Off-Balance reading fell from 20% to 3% where the boss died 8 s into a 10 s fight with the debuff still open and no FADED line.

## Decisions

- **The fallback is decided per fight, not per rule or at record time.** A `boss` rule records spans on every hostile, tagged with the unit's kind, and the snapshot decides from the fight's units whether a boss was hit. The engine's answer (`CombatEncounter.fight_units`: the players and the hostiles the group hit, with the time each arrived and died or was removed) is preferred over inferring from the spans, so a boss the group hit but the effect never reached still makes it a boss fight reading 0%, rather than a pack reading. Alone, the tracker infers from its spans, which the unit tests use.
- **The count is distinct mobs reached, of the pack.** "How many mobs are affected" is answered by distinct units the effect was on at any time, and the pack is the mobs the group hit plus any a tracked effect landed on, so the denominator is the same for every rule on the line and never smaller than the count. The peak at once was measured too but not shown: one number more per item on an already long line.
- **`each` rather than changing `uptime`.** The taunt needs its per-boss mean; a debuff's union is what 0.8.0 specified and what "was it up?" means. A third measurement word keeps both and lets `each` serve any rule (per-player Major Courage). `each` and `stacks` do not combine.
- **The built-ins are removed, not shadowed.** One mechanism for the line: the engine's buff tables, global buff transfer at BEGIN_COMBAT, taunt spans, their diagnostics and `_covered_ms` go; `player_taunts` (who taunted with what) stays. The ids move into `UPTIME_LINE_RULES`, the first seven of `DEFAULT_RULES` and `EXAMPLE_RULES`.
- **An older config is topped up by name, once.** `tracking.version` marks the layout; a saved text without it gets the uptime line's lines it lacks in front, so a user's own `Taunt` rule stays theirs. Nothing is written at startup; the version is saved with the next Save and the top-up is idempotent.
- **Full names on the line.** `Major Courage:87%` rather than `MCourage:87%`: the examples already use full names, and a user who prefers the short form renames the rule.

## Risks / Trade-offs

- [The line is longer] → fourteen default items, full names; duo and solo fights now show the group buffs at 0%. Hiding items that read 0 would answer this and is the open question from 0.8.0; not decided here.
- [A boss fight the engine does not see as one] → a boss the group never hit (untouched, or only taunted without damage) makes the fight a pack fight; taunting skills all deal damage, so the case is theoretical.
- [`each` windows start at the unit's UNIT_ADDED or the fight's start] → a hostile that becomes hostile later (UNIT_CHANGED) is measured from its arrival, slightly over its life; bosses are present at the pull.
- [The experimental strip keeps its own built-in rows] → a rule named like a built-in row (Major Courage, Taunt) is not drawn twice; the strip's label uses the recorder's union, the line the rule's measure.

## Migration Plan

Config: `tracking.version` added (2); a stored rules text without it is topped up on read. Users who never saved Settings get the new defaults. Rollback: delete the seven lines, or the config's tracking section.
