# Proposal: The uptime line as rules, and boss debuffs in trash packs

## Why

Two requests from the maintainer on 2026-10-09, the day 0.8.0 shipped tracked effects:

- A `boss` rule reads nothing in a fight without a boss, yet most fights are trash packs (281 of 376 in twelve logs of 2026), where debuffs such as Major Vulnerability and Roar of Alkosh land on many mobs at once. Players want to see those fights measured, and how many of the pack's mobs the effect reached.
- The six group buffs and the taunt were still tracked in code and could not be removed from the line. They should be rules like the rest, so anyone can delete, rename or edit them, and always recoverable from the example picker.

Measuring the real logs for this also found that the game does not always write FADED for an effect on a unit that dies or is removed, so a tracked span stayed open and counted into every later fight of the zone (124 of the 376 fights ended with such a span).

## What Changes

- **A boss rule in a fight without a boss measures the pack**: every hostile the group fought, and both it and an `enemies` rule say how many of the pack's mobs the effect reached: `Alkosh:45% on 7 of 12 mobs`. The timeline row says `mobs`. In a boss fight nothing changes.
- **`each`**, a third measurement: the effect on every unit of the scope separately, over the time that unit was alive in the fight, averaged. It is the taunt's measure from issue #9 (each boss to its death, the mean over the bosses) made available to any rule.
- **The uptime line is rules only**: `Major Courage`, `Major Force`, `Major Slayer`, `Powerful Assault`, `Lucent Echoes`, `Pearlescent Ward` on group and `Taunt = 38254 on boss each` are the first seven default rules and the first seven examples; the engine's own group buff and taunt tracking is removed. A rules text saved before this change is given the seven lines once, by name.
- **A unit's death or removal ends its spans**, and a zone change ends the spans on hostiles and pets.

## Capabilities

### Modified Capabilities

- `tracked-effects`: the pack fallback and mob count, the `each` measurement, the default rules and examples, the upgrade of a saved rules text, and spans ending with their unit.

## Impact

- Engine: `effect_rules` (spans tagged with the unit's kind, `each`, the pack, `forget_unit`, `zone_changed`), `esolog_tail` (the built-in buff and taunt tracking removed, `fight_units`, deaths and removals and zone changes reported to the tracker), `app_config` (the one-time top-up, `tracking.version`).
- GUI: the strip's scope column shows what a rule measured; Settings help text.
- Behaviour: group buffs appear whatever the group size and read 0% when never seen; the taunt reads as before.
- Docs: README, user guide, changelog, design notes.
