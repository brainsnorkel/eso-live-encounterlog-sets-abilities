# Proposal: Tracked effects (issue #10)

## Why

The uptime line knows six group buffs and the taunt, chosen in code. Raid leads and players want to watch other things fight by fight: a set's debuff on the boss, how often the boss was Off-Balance, how many Crux an Arcanist held, the stacks of Touch of Z'en, a buff that only pets give. Every such question today means a code change and a release. And the people who know which ability ids matter already keep them in HyperTools, the in-game tracker addon, and share them as text.

## What Changes

- **Tracked effects, by rule**: the user names effects by their ability ids and asks for the effect's uptime or its stack count on a kind of unit: the logging player, any group member, a group member's pet, a boss, or any enemy. Each rule adds an item to the fight's uptime line, in the fight pane and in copied text, whatever the group size.
- **A plain text rule format**, one rule per line, kept in Settings and shareable by copy and paste: `Off-Balance = 45902 62988 39077 on boss`, `Crux = 184220 on self stacks`. A line that will not parse is reported with its number and skipped; the others still work.
- **HyperTools exports accepted as rules**: a line that starts with `$` is a HyperTools tracker export string; its name, ability ids and target become a rule, groups included.
- **Bundled examples**: a fresh install starts with the four examples of issue #10 (Off-Balance on the boss as a union of its ids, Touch of Z'en stacks on the boss, Crux stacks on self, Morag Tong on the boss), and Settings can restore them.
- **Timeline rows** (when the experimental strip is on): one row per rule after the built-in rows; a stacking effect's bar is drawn with a height that follows the stack count.

## Capabilities

### New Capabilities

- `tracked-effects`: user-defined effect rules in a shareable text format (with HyperTools import), measured per fight by uptime or stacks on a chosen kind of unit, shown on the uptime line and the timeline strip.

### Modified Capabilities

<!-- none: the built-in group buffs, the taunt and the experimental timeline keep their requirements -->

## Impact

- Engine: a new `effect_rules` module (rule text, HyperTools decoding, the tracker); the effect handler feeds it; the fight entry gains `tracked`; the analyzer learns which player writes the log and which enemies are bosses (both already in the log).
- Config: `tracking.rules`, a text, defaulting to the bundled examples.
- GUI: a text box with live parse feedback in Settings; rows in the timeline strip.
- Docs: README, user guide, design notes, changelog.
- No new dependency. Existing fights and goldens are unchanged when no rule matches.
