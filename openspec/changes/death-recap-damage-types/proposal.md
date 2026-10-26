# Proposal: The kinds of damage, in the death recap and the build window

## Why

Issue #73: the death recap lists every hit and heal of the last five seconds but never adds them up, so a reader cannot see what kind of damage killed them, and nothing in the app shows what kind of damage a player takes over a fight or deals in one. The Warfare champion point stars act on exactly these splits (direct against damage over time, area against single target, Magical against Martial, direct heals against heals over time), so a player picking stars has no figure in the app to judge by. The encounter log carries the damage type and the result on every hit, and the cast id that tells an area hit from a single one, so the figures can be read from what the app already records; the maintainer's priority is a succinct presentation of the splits, the champion point angle second.

## What Changes

- **Each death gets a summary of its last five seconds**, under the "Killed by" line and above the event table: the damage that reached health, split direct / over time, area / single target and Martial / Magical (with Oblivion and the unresisted kinds, fall damage and drowning, named apart), then the damage types behind the Magical and Martial sides (fire 55%, physical 45%), what got through a block, what shields absorbed, what was dodged, the healing that landed against the overheal, and the killing blow's overkill. Each split is a two-colour bar with its percentages, or a line of text where a bar would be clutter.
- **The recap also sums the whole fight**: a "Damage taken this fight" block at the top of the window with the same splits over every hit the player took in the fight, and the abilities that did the most of it with their kinds. Over the Dreadsail Reef log of 2026-09-02 (550 deaths) a death's five seconds is usually one mechanic, often a single hit that is the whole table, so the fight total is what a champion point choice has to be judged on.
- **Each recap row names its kind**: the damage type (fire, physical, oblivion) joins the result in the Result column, and a hit from a cast that struck more than one player says so ("area · hit 8 players").
- **The build window gains a "Damage dealt" section** before Penetration, built from the damage record the damage window already keeps: the same three splits over the player's damage in the fight, the damage types, and the share of ticks, so a damage dealer can read whether their build is a direct, area, Magical build. Nothing is added to the damage window.
- **Area or single target comes from the log, not a list**: a hit is "area" when its cast (the same source and cast id) struck two or more distinct units in the fight. In 87 split logs (11.6 million combat lines) every hostile hit on a player carries a cast id; the mechanics that kill groups (Oppressive Bolts, Maelstrom, Grievous Pulse) hit up to 12 players on one cast id, and UESP's skill table calls several of them "Enemy", so a table would misread them. For a player's own skills, where one boss hides an area skill, UESP's target field (Area, Cone, Ground, Enemy) is bundled from the reply the esobuild export already caches, no new request to UESP, and the cast rule decides when the table does not know.
- **Hovering a split names the Warfare stars that act on it** (Master-at-Arms and Thaumaturge, Biting Aura and Deadly Aim, War Mage and Mighty for damage dealt; Ironclad and Enduring Resolve, Unassailable and Duelist's Rebuff, Elemental Aegis and Hardy for damage taken; Focused Mending and Swift Renewal, Blessed and Quick Recovery for healing), with the game's tooltip text and a link to the star's ESO-Hub page. The app never guesses which stars a player has: that is not in the log.
- **Not done, and said in the guide**: melee against ranged (the log has no range; its unit positions are in map units whose scale differs by map, and no Warfare star reads it), how much a block or a resistance saved (the log writes what got through), and critical hits taken (monsters do not crit players: 0.1% of the damage players took in the survey).
- Documentation: the user guide's "Death recaps" and "A player's build" sections and its "What the log cannot show" list, the README's death recap line, the changelog, a recap screenshot, design notes in the code extracted into docs/design.md.

## Capabilities

### New Capabilities

- `damage-kinds`: how a hit or heal in the log is classified (direct or over time, area or single target, Martial, Magical or neither, blocked, absorbed, avoided, overheal, overkill), what the app can and cannot tell from the log, and the Warfare stars named for each side.
- `death-recap-damage-kinds`: what the death recap window shows per death and per fight about the kinds of damage taken and healing received.
- `build-damage-dealt-kinds`: the build window's "Damage dealt" section.

### Modified Capabilities

(none; the project keeps no main specs)

## Impact

- New `src/damage_kinds.py` (engine side, no Qt): the classification tables, the per-fight cast index that tells area from single target, a per-player "damage taken" aggregate, the summary both renderers draw from, and the Warfare star table.
- `src/death_recap.py`: a recap event keeps its damage type and whether its cast hit more than one player; pure overheals are kept for the overheal sum and still left out of the rows; a recap carries the fight-to-date "taken" aggregate.
- `src/esolog_tail.py`: the recap branch of `_handle_combat_event` feeds the cast index and the aggregate; the player's fight dict gains a `taken` key.
- `src/damage_stats.py`: `AbilityDamage` keeps damage by type, tick damage and area damage; `PlayerDamage.snapshot` adds a `kinds` summary.
- `src/gui/death_render.py` and `src/gui/build_render.py`: the bars, the fight block, the Result column's type, the Damage dealt section, the star hover text (the fight pane's tooltip mechanism); `src/gui/death_recap_dialog.py` passes the hover map to its view, which it does not do today.
- New `scripts/generate_ability_targets.py` and `data/skills/ability_targets.json` (player skills' target kinds from the cached UESP reply, CC-BY-SA attribution as the other UESP tables carry).
- Tests: `tests/unit/test_death_recap.py`, `test_death_recap_gui.py`, `test_damage_attribution.py`, `test_build_window_gui.py`, a new `test_damage_kinds.py`; the golden fixture's expected entries gain the new keys.
- Docs: user guide, README, CHANGELOG, `docs/screencaps/death-recap.png` retaken, `scripts/build_design_doc.py` gains the topic, `docs/design.md` regenerated.
- Fight entries recorded before the change show "not recorded" where the new blocks would be; no config change; no new dependency (checked 2026-10-27: the 0.14.4 build's CPython 3.14.9, PySide6 6.12.0, Pillow 13.0.0, PyInstaller 6.22.3, setuptools 84.2.1 and pip 26.2.2 are the newest on PyPI with no OSV advisory; CPython 3.14.10 is tagged and the `3.14` pin takes it when python.org publishes the Windows build).
