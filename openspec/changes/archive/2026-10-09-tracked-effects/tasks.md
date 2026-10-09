# Tasks

## 1. Rules and tracker (engine)

- [x] 1.1 `effect_rules.py`: the line format parser with per-line errors, the HyperTools string decoder mirroring Transmission.lua and the tracker walk, and `EffectTracker` (spans per rule, unit and id; snapshot with uptime, mean and peak stacks, text and fight-relative intervals; prune); verified by `tests/unit/test_effect_rules.py` (16 tests)
- [x] 1.2 Engine wiring: `PlayerInfo.is_local` from UNIT_ADDED, `_unit_kind` for the scopes, the effect handler feeding the tracker with the stack count, `FightHistoryEntry.tracked`, the uptime line extended after the taunt whatever the group size, reset on BEGIN_LOG; verified by the full suite passing with the golden fights unchanged
- [x] 1.3 Engine integration test with synthetic log lines: a boss debuff under two ids, Crux stacks on the local player, a pet-only scope, a pre-pull span; verified by `tests/unit/test_tracked_effects_engine.py`
- [x] 1.4 Replay the bundled examples through two real trial logs and record the results in the design notes (Off-Balance per fight, Crux on the logging player); verified by the numbers matching the survey's independent count within a percent

## 2. Settings

- [x] 2.1 `tracking.rules` in the config defaults (the bundled examples) and `build_analyzer` building the tracker from it; verified by a round trip through a reloaded AppConfig in the Settings tests
- [x] 2.2 The Settings box: monospace text, live count and error line, an Examples… button opening a picker of example rules (tick, Add to rules, Copy; present names start unticked) that appends the ticked lines and reports how many, saved by Save; verified by `tests/unit/test_settings_dialog.py` cases for the status text and the round trip

## 3. Timeline rows

- [x] 3.1 `TimelineStrip` takes the fight's tracked items as extra rows after the built-in ones, labelled with the rule's text, hover naming the unit; verified by an offscreen render test counting rows
- [x] 3.2 Stack bars drawn by height (count over the fight's peak); verified by a render test reading pixel heights of a 1-then-3-stack interval

## 4. Documentation

- [x] 4.1 README (Settings and "What the analysis is based on"), the user guide (a Tracked effects section with the rule format and a HyperTools paste), the changelog entry, and `effect_rules` added to the design doc topics and regenerated; verified by `python scripts/build_design_doc.py` succeeding and the user guide showing the format
