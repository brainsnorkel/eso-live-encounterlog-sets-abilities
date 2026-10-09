# Tasks

## 1. Survey

- [x] 1.1 Replay twelve 2026 split logs through the engine with the effects of interest on `enemies` scope: fights without a boss, mobs hit, mobs reached and at once per effect, spans left open on dead or removed units, the built-in group buffs and taunt against the same effects as rules; verified by the numbers in `effect_rules`'s module docstring and the changelog

## 2. Rules and tracker

- [x] 2.1 `effect_rules`: spans tagged with the unit's kind, a `boss` rule recording every hostile, the snapshot's fallback to the pack with `units`, `mobs_reached` and `mobs` per item and the `on N of M mobs` text, the `each` measurement with per-unit windows, `forget_unit`, `zone_changed`, a sweep-based `_measure`, `UPTIME_LINE_RULES`, the fourteen defaults and the examples, `lines_to_add`; verified by `tests/unit/test_effect_rules.py` (29 tests)
- [x] 2.2 Engine: the built-in buff and taunt tracking removed, `EnemyInfo.added_at` and `removed_at`, `CombatEncounter.fight_units`, deaths, removals and zone changes reported to the tracker, the uptime line built from the rules alone; verified by `tests/unit/test_tracked_effects_engine.py`, `test_taunt.py`, `test_group_buff_uptime.py`, `test_combat_resume.py` and the golden fights unchanged
- [x] 2.3 Replay the sample through the committed and the changed engine: every fight field but the uptime line identical, the group buffs and the taunt compared item by item; verified by the comparison in the session notes

## 3. Settings and config

- [x] 3.1 `tracking.version` and the one-time top-up of an older rules text in `AppConfig.reload`; verified by `tests/unit/test_app_config.py`
- [x] 3.2 Settings help text and group title; the picker's `lines_to_add` moved to `effect_rules`; verified by `test_settings_dialog.py` and `test_examples_dialog.py`

## 4. Timeline strip

- [x] 4.1 The scope column shows what a rule measured (`mobs` in a fight without a boss); verified by `test_timeline_strip.py`

## 5. Documentation

- [x] 5.1 README (uptime line, Settings, Tracked effects, the strip), the user guide, the changelog, the design notes regenerated from the docstrings (`scripts/build_design_doc.py`, the group buff topic folded into tracked effects)
