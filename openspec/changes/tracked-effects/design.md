# Design: Tracked effects

## Context

See proposal.md for why. The engine already tracks six group buffs by ability id (`group_buff_ids`), the taunt debuff by one id, and an experimental timeline of seven effects (`buff_timeline.TRACKED_TIMELINE_EFFECTS`), each as spans in raw log milliseconds that a fight window is read out of. Every effect arrives as an EFFECT_CHANGED line whose fields the engine already decodes (`extract_effect_fields`: change, ability id, source, target), with the stack count in its second field. The engine knows players, their pets (`pet_ownership`), hostiles and the game's boss flag (`EnemyInfo.is_boss`), but not which player writes the log; UNIT_ADDED carries that flag.

What nine trial and dungeon logs of 2026 showed, measured before this design: Off-Balance on a boss comes under several ids at once (45902 for most sources, 62988 Elemental Blockade, 39077 Unstable Wall, 34733, 20806, 130139), union uptime 4 to 28% per trial boss fight; stack changes arrive as UPDATED lines with the new count (Crux 1 to 3 on the Arcanist, Touch of Z'en to 5 on enemies, Arms of Relequen to 10); pet-applied buffs (a Glyphic's heal, Major Protection from a netch) land on players like any other buff. HyperTools, the in-game tracker users already keep ids in, exports a tracker as nested `$...&` records (`Transmission.lua`), with `name`, `IDs`, `target` (Yourself, Group, Boss, Current Target) and effect events that carry their own `Ids`.

## Goals / Non-Goals

Goals: any effect by id, measured by uptime or stacks on a chosen kind of unit; rules as text that survives copy and paste; HyperTools strings accepted as is; no cost when there are no rules.

Non-goals: per-player breakdowns (who had it), rules by effect name (names differ by language and one name covers several ids), conditions beyond scope (duration thresholds, zone, class), editing HyperTools strings back out, and tracking before the first fight of a session.

## Decisions

- **A line format of our own, with HyperTools strings alongside.** `Name = ids on scope [stacks]` reads at a glance, diffs well in chat, and needs no quoting. HyperTools strings are kept verbatim rather than translated on paste, so a user can re-paste what a friend sent without learning the line format; words after the string override its scope and measurement. Alternatives: JSON (hostile to paste by hand), a table editor only (not shareable as text).
- **Scope is about the target only.** A rule says whose effect counts (self, group, pets, boss, enemies), never who cast it: that is what the uptime line answers and it needs no special case for pets or other players as casters. The engine classifies a target through what it already keeps (players and the new `is_local` flag, `pet_ownership`, `enemies` with `is_hostile` and `is_boss`).
- **Union over ids and over units.** A rule's ids are one effect to the user (Off-Balance from any skill); its uptime is the time the effect was on any unit of the scope. Each id runs its own span on each unit so that overlapping ids do not cut each other short; the measurement merges them. For stacks, the level at a moment is the highest among the units it is on, so a boss rule with two bosses reads the fuller one.
- **Spans in raw log time, read per fight.** The tracker keeps open and closed spans like the timeline recorder, snapshots a fight window (pre-pull spans run in, open spans run to the end) and prunes after the fight has been published, so a fight the game cuts in two can be read again when it really ends.
- **Measured whatever the group size.** The built-in line needs three players; a rule can be about the logging player alone, so its items are added regardless.
- **Rules parsed in two places.** The engine parses the config text when the analyzer is built and ignores bad lines; Settings parses as the user types and shows the count and the errors. One parser, two callers.
- **Timeline rows by height.** A stacking rule's bar height is the stack count over the rule's peak in that fight, which shows a ramp (Crux, Z'en) without a second axis.

## Risks / Trade-offs

- [A rule names an id the log never writes] → it reads 0%, which is itself the answer; the status line in Settings cannot know, since the log decides.
- [The `self` scope needs the local-player flag] → every log the app has seen carries it on the logging player's UNIT_ADDED; a reviewed log from another player's client marks that player as self.
- [Many rules on a busy fight] → the tracker does one dictionary lookup per EFFECT_CHANGED line for ids it does not know; spans are pruned per fight; a rule on `enemies` in a trash fight can hold hundreds of spans, still small.
- [HyperTools changes its format] → the decoder mirrors `Transmission.lua` of the installed version; a string it cannot read is one skipped line with an error, never a crash.
- [An example id nobody has verified in a log misleads] → the bundled examples are only ids the logs showed; Morag Tong, whose debuff no log of ours carries, is left for a user who knows its id.

## Migration Plan

Config gains `tracking.rules` with the examples as its default; an existing config without it gets the examples on first read. Nothing else changes for a user who never opens Settings, except four new items on the uptime line, which they can delete there. Rollback: remove the rules text.
